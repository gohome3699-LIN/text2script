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
import json
import os
import re
import sys
from datetime import datetime

# 让上级目录的 text2script 规则模块可导入
PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from flask import Flask, jsonify, make_response, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

import input_parser as ip
import storyboard as sb
import auth
import history
import tracking
import usage

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTS = {".txt", ".md", ".docx"}
MAX_CHARS = 50000  # 单次转换的输入上限（字符）
DURATION = 75      # 集目标时长（秒）
SHOTS_PER_MINUTE = 20  # 分镜密度（镜/分钟）

AI_NOTICE = "本内容由 AI 生成，仅供参考"

# 落地页 email 订阅收集（M1：50 个有效 email）
SUBSCRIBERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "subscribers.json"
)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _set_refresh_cookie(resp, token: str):
    """通过 HttpOnly Cookie 下发长期 Refresh Token。"""
    resp.set_cookie(
        auth.REFRESH_COOKIE,
        token,
        max_age=int(auth.REFRESH_TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="Lax",
        secure=auth.COOKIE_SECURE,
        path="/",
    )


def _clear_refresh_cookie(resp):
    resp.delete_cookie(auth.REFRESH_COOKIE, path="/")


def _auth_response(user: dict, status: int = 200):
    """登录/注册成功：签发 access token + refresh cookie。"""
    access_token = auth.create_access_token(user["id"])
    refresh_token = auth.issue_refresh_token(user["id"])
    resp = make_response(jsonify({
        "ok": True,
        "user": auth.public_user(user),
        "access_token": access_token,
    }), status)
    _set_refresh_cookie(resp, refresh_token)
    return resp


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
        # M2 整合：需登录；额度预检（不足提前拒绝，避免白做转换）
        user = auth.current_user()
        if not user:
            raise ApiError("auth_required", "請先登入後使用文轉劇", status=401)
        before = usage.get_usage(user["id"])
        if before["remaining"] <= 0:
            raise ApiError(
                "quota_exceeded",
                "本月額度已用完，請下月再試或升級方案",
                before,
                status=402,
            )
        file = request.files.get("file")
        text_raw = request.form.get("text") or ""
        if file and file.filename:
            raw = read_uploaded(file)
        elif text_raw:
            # 传原始值（可能为空白），空文本由 convert 判为 empty_text
            raw = text_raw
        else:
            raise ApiError("no_input", "请上传文件或输入文本")
        data = convert(raw)
        # 转换成功才消耗额度并写入历史（每次 1 次）
        data["usage"] = usage.consume(user["id"], 1)
        history.append_history(user["id"], data)
        # M1 T4 轉換追蹤：轉換成功事件（用於渠道漏斗：來源→註冊→實際使用）
        tracking.record_event("convert", {
            "user_id": user["id"],
            "email": user.get("email"),
            "cleaned_length": data.get("cleaned_length"),
            "num_episodes": data.get("num_episodes"),
        })
        return jsonify(data)
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


@app.route("/landing")
def landing():
    """落地页（M1）：介绍 + 暂定定价 + email 订阅收集。"""
    return render_template("landing.html")


@app.route("/subscribe", methods=["POST"])
def subscribe_api():
    """落地页 email 订阅：保存到 web/data/subscribers.json（文件方式）。"""
    try:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return jsonify(
                {"ok": False, "error_code": "bad_email",
                 "error": "请输入有效的邮箱地址"}
            ), 400

        subscribers = []
        if os.path.exists(SUBSCRIBERS_FILE):
            try:
                with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    subscribers = data
            except (ValueError, OSError):
                subscribers = []

        # 去重：已订阅同邮箱返回成功但标记 duplicate（不重复计数订阅事件）
        for row in subscribers:
            if str(row.get("email", "")).strip().lower() == email:
                return jsonify({"ok": True, "duplicate": True})

        # M1 T4 來源追蹤：前端提交的 utm/referrer/page（白名单过滤）
        source = tracking.sanitize_source(payload.get("source"))
        subscribers.append({
            "email": email,
            "subscribed_at": datetime.now().isoformat(timespec="seconds"),
            "source": source or None,
        })
        os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as fh:
            json.dump(subscribers, fh, ensure_ascii=False, indent=2)
        tracking.record_event("subscribe", {"email": email, **source})
        return jsonify({"ok": True, "duplicate": False})
    except Exception as exc:  # noqa: BLE001 - 对外统一错误信息
        return jsonify(
            {"ok": False, "error_code": "server_error",
             "error": f"服务内部错误：{exc}", "detail": {"msg": str(exc)}}
        ), 500


@app.route("/api/auth/signup", methods=["POST"])
def signup_api():
    """M2 注册（T13a 账号）：Email＋密码（argon2），自动登录。"""
    try:
        payload = request.get_json(silent=True) or {}
        user = auth.create_user(
            str(payload.get("email") or ""), str(payload.get("password") or "")
        )
        # M1 T4 來源追蹤：註冊事件（若前端帶有 UTM 來源則一併歸因）
        source = tracking.sanitize_source(payload.get("source"))
        if source:
            tracking.record_event(
                "signup", {"user_id": user["id"], "email": user["email"], **source}
            )
        return _auth_response(user, status=201)
    except auth.AuthError as exc:
        return jsonify(
            {"ok": False, "error_code": exc.code, "error": exc.message}
        ), exc.status
    except Exception as exc:  # noqa: BLE001
        return jsonify(
            {"ok": False, "error_code": "server_error",
             "error": f"服务内部错误：{exc}"}
        ), 500


@app.route("/api/auth/login", methods=["POST"])
def login_api():
    """M2 登录：验证 Email＋密码，签发 access + refresh。"""
    try:
        payload = request.get_json(silent=True) or {}
        user = auth.authenticate(
            str(payload.get("email") or ""), str(payload.get("password") or "")
        )
        # M1 T4 來源追蹤：登入事件（僅記錄，不影響登入流程）
        source = tracking.sanitize_source(payload.get("source"))
        if source:
            tracking.record_event(
                "login", {"user_id": user["id"], "email": user["email"], **source}
            )
        return _auth_response(user)
    except auth.AuthError as exc:
        return jsonify(
            {"ok": False, "error_code": exc.code, "error": exc.message}
        ), exc.status
    except Exception as exc:  # noqa: BLE001
        return jsonify(
            {"ok": False, "error_code": "server_error",
             "error": f"服务内部错误：{exc}"}
        ), 500


@app.route("/api/auth/logout", methods=["POST"])
def logout_api():
    """M2 登出：撤销 refresh token 并清除 Cookie。"""
    token = request.cookies.get(auth.REFRESH_COOKIE)
    user = auth.current_user()
    if user:
        auth.revoke_all_for_user(user["id"])
    elif token:
        auth.consume_refresh_token(token)
    resp = make_response(jsonify({"ok": True}))
    _clear_refresh_cookie(resp)
    return resp


@app.route("/api/auth/refresh", methods=["POST"])
def refresh_api():
    """M2 续期：用 refresh cookie 换取新的 access + refresh（rotation）。"""
    token = request.cookies.get(auth.REFRESH_COOKIE)
    user_id = auth.consume_refresh_token(token)
    if not user_id:
        resp = make_response(jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "登录已过期，请重新登录"}
        ), 401)
        _clear_refresh_cookie(resp)
        return resp
    user = auth.find_user_by_id(user_id)
    if not user:
        resp = make_response(jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "账号不存在，请重新登录"}
        ), 401)
        _clear_refresh_cookie(resp)
        return resp
    return _auth_response(user)


@app.route("/api/me")
def me_api():
    """M2 当前用户：资料 + 本月额度。"""
    user = auth.current_user()
    if not user:
        return jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "请先登录"}
        ), 401
    return jsonify({
        "ok": True,
        "user": auth.public_user(user),
        "usage": usage.get_usage(user["id"]),
    })


@app.route("/api/usage/consume", methods=["POST"])
def usage_consume_api():
    """M2 额度消耗（T13b）：供前端 /convert 前调用或由后端门控复用。

    当前规则：每次文转剧转换消耗 1 次。
    """
    user = auth.current_user()
    if not user:
        return jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "请先登录"}
        ), 401
    try:
        n = int((request.get_json(silent=True) or {}).get("n", 1))
    except (TypeError, ValueError):
        n = 1
    try:
        result = usage.consume(user["id"], n)
        return jsonify({"ok": True, "usage": result})
    except usage.UsageError as exc:
        return jsonify(
            {"ok": False, "error_code": exc.code,
             "error": exc.message, "detail": exc.detail}
        ), 402


@app.route("/login")
def login_page():
    """M2 登入/註冊頁（手機版優先）：前端處理雙模式與 token 保存。"""
    return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    """M2 儀表板：使用概況＋歷史記錄（資料由前端拉 /api/me、/api/history）。"""
    return render_template("dashboard.html")


@app.route("/usage")
def usage_page():
    """M2 使用頁：文轉劇操作流程（登入用戶專用，前端未登入跳轉）。"""
    return render_template("usage.html")


@app.route("/api/history")
def history_api():
    """M2 儀表板歷史記錄：需登入，按時間倒序回傳（最多保留最近 50 條）。"""
    user = auth.current_user()
    if not user:
        return jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "請先登入"}
        ), 401
    return jsonify({"ok": True, "history": history.get_history(user["id"])})


@app.route("/api/tracking")
def tracking_api():
    """M1 T4 來源與轉換追蹤查詢：需登入，回傳渠道統計與最近事件。

    目前面向開發者/運營自查；正式對外前可再加管理角色權限。
    """
    user = auth.current_user()
    if not user:
        return jsonify(
            {"ok": False, "error_code": "auth_required",
             "error": "請先登入"}
        ), 401
    return jsonify({"ok": True, "stats": tracking.stats()})


@app.errorhandler(413)
def too_large(_):
    return jsonify(
        {"ok": False, "error_code": "file_too_large",
         "error": "上传文件过大（超过 10MB）", "detail": {}}
    ), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)