# -*- coding: utf-8 -*-
"""T06 输入解析器命令行示例入口。

用法（在 text2script/ 目录下）：
    python example.py --text "一句话创意：外卖小哥获得读心术"
    python example.py --file story.txt
    python example.py --file story.docx [--sheet 1]

支持 .txt 与 .docx（.docx 需要 python-docx，未安装时自动提示）。
"""

import argparse
import sys

import input_parser as ip

PROMPT_TEMPLATE = (
    "你是一位短剧编剧。请把以下故事素材作为剧本底稿来源，"
    "按强钩子拆集规则拆分为每集 60~90 秒的短剧集，"
    "每集一个核心冲突，集末必须留下悬念/反转/危机。\n"
    "【素材原文】\n{输入原文}"
)


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_docx_file(path: str) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        sys.exit("读取 .docx 需要 python-docx，请先安装：python -m pip install python-docx")
    document = docx.Document(path)
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="T06 输入解析器示例")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="直接传入故事文本")
    src.add_argument("--file", help="读取故事文件（.txt / .docx）")
    parser.add_argument("--no-template", action="store_true", help="不注入提示词模板")
    args = parser.parse_args()

    if args.text:
        raw = args.text
    else:
        path = args.file
        if path.lower().endswith(".docx"):
            raw = read_docx_file(path)
        else:
            raw = read_text_file(path)

    result = ip.parse_input(
        raw,
        template=None if args.no_template else PROMPT_TEMPLATE,
    )

    print("=" * 60)
    print(f"输入类型: {result.input_type_label} ({result.input_type})")
    print(f"需要扩写为剧本底稿: {'是' if result.needs_expansion else '否'}")
    print(f"原始字数: {result.original_length} -> 清洗后: {result.cleaned_length}")
    print(f"分段数量: {result.chunk_count}")
    if result.sensitive_hits:
        print(f"⚠ 命中红线类别: {', '.join(result.sensitive_hits)}（请人工确认后继续）")
    else:
        print("红线检查: 未命中")
    print("=" * 60)

    for i, (chunk, rendered) in enumerate(zip(result.chunks, result.rendered or [None] * len(result.chunks)), 1):
        print(f"\n--- 第 {i} 段（{len(chunk)} 字）---")
        if rendered:
            print(rendered)
        else:
            print(chunk[:200] + ("…" if len(chunk) > 200 else ""))


if __name__ == "__main__":
    main()