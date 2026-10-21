# -*- coding: utf-8 -*-
"""纯文转剧本分镜 · 网页版（Flask）。

输入：文件上传（.docx / .txt / .md）或直接粘贴 / 打字文本
输出：纯文字档分镜稿（.txt），超过 800 字按分镜节点分段（每镜一段，空行分隔）

复用 text2script 规则引擎，与 CLI 输出一致：
    python text2script.py --file story.txt --format text

输入语言匹配：中文输入 → 中文输出；英文输入 → 英文输出（输出语言字段
language: zh / en 随 convert 返回）。界面语言：简体中文 / 繁体中文 /
English（前端切换，仅作用于界面文案；输入与输出内容不做翻译）。
后端以 error_code + detail 返回错误，由前端按语言渲染。

启动（在 text2script/web 目录下）：
    python app.py
    浏览器访问 http://127.0.0.1:5000
"""

import io
import os
import sys

# 让上级目录的 text2script 规则模块可导入
PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

import input_parser as ip
import storyboard as sb

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTS = {".txt", ".md", ".docx"}
MAX_CHARS = 50000  # 单次转换的输入上限（字符）
DURATION = 75      # 集目标时长（秒）
SHOTS_PER_MINUTE = 20  # 分镜密度（镜/分钟）

AI_NOTICE = "本内容由 AI 生成，仅供参考"


class ApiError(Exception):
    """带错误码的业务异常，前端按 error_code 翻译展示。"""

    def __init__(self, code: str, message: str, detail: dict | None = None,
                 status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.status = status


def read_uploaded(file_storage) -> str:
    """读取上传文件：.docx 提取段落文本；.txt/.md 尝试 utf-8 / gb18030 解码。"""
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        raise ApiError(
            "bad_ext",
            f"不支持的文件类型：{ext or '无扩展名'}，请上传 .txt / .md / .docx",
            {"ext": ext or "(none)"},
        )
    raw_bytes = file_storage.read()

    if ext == ".docx":
        try:
            import docx
        except ImportError:
            raise ApiError(
                "missing_docx",
                "服务器缺少 python-docx，无法读取 .docx 文件",
                status=500,
            )
        try:
            document = docx.Document(io.BytesIO(raw_bytes))
        except Exception:
            raise ApiError(
                "docx_bad",
                "无法解析该 .docx 文件，请确认文件未损坏或不是伪装的文档",
            )
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())

    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def convert(raw_text: str) -> dict:
    """核心转换：解析 -> 拆集 -> 分镜 -> 纯文字档渲染。"""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ApiError("empty_text", "请输入或上传至少一段故事文本")
    if len(raw_text) > MAX_CHARS:
        raise ApiError(
            "too_long",
            f"文本过长（{len(raw_text)} 字），请控制在 {MAX_CHARS} 字以内，或拆成多段转换",
            {"n": len(raw_text)},
        )

    parse = ip.parse_input(raw_text)
    plan = sb.build_storyboard_plan(
        raw_text,
        template=None,
        target_duration=DURATION,
        shots_per_minute=SHOTS_PER_MINUTE,
    )

    # 超过 800 字：按分镜节点分段落（每个分镜一段，空行分隔）
    break_by_shot = parse.cleaned_length > 800
    content = sb.render_storyboard_text(plan, break_by_shot=break_by_shot)

    problems = sb.validate_storyboard(plan)
    language = getattr(plan, "language", "zh")
    return {
        "ok": True,
        # content 为纯分镜稿；AI 声明由前端按界面语言附加（页面展示 / 复制 / 下载）
        "content": content,
        "ai_notice": AI_NOTICE,
        "input_type": plan.input_type,
        "input_type_label": plan.input_type_label,
        "language": language,  # 输出语言：zh（中文输入）/ en（英文输入）
        "cleaned_length": parse.cleaned_length,
        "break_by_shot": break_by_shot,
        "num_episodes": len(plan.episodes),
        "warnings": plan.warnings,
        "problems": problems,
        "sensitive_hits": plan.sensitive_hits,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_api():
    try:
        file = request.files.get("file")
        text_raw = request.form.get("text") or ""
        if file and file.filename:
            raw = read_uploaded(file)
        elif text_raw:
            # 传原始值（可能为空白），空文本由 convert 判为 empty_text
            raw = text_raw
        else:
            raise ApiError("no_input", "请上传文件或输入文本")
        return jsonify(convert(raw))
    except ApiError as exc:
        return jsonify(
            {"ok": False, "error_code": exc.code,
             "error": exc.message, "detail": exc.detail}
        ), exc.status
    except RequestEntityTooLarge:
        return jsonify(
            {"ok": False, "error_code": "file_too_large",
             "error": "上传文件过大（超过 10MB）", "detail": {}}
        ), 413
    except Exception as exc:  # noqa: BLE001 - 对外统一错误信息
        return jsonify(
            {"ok": False, "error_code": "server_error",
             "error": f"服务内部错误：{exc}", "detail": {"msg": str(exc)}}
        ), 500


@app.errorhandler(413)
def too_large(_):
    return jsonify(
        {"ok": False, "error_code": "file_too_large",
         "error": "上传文件过大（超过 10MB）", "detail": {}}
    ), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)