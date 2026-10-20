# -*- coding: utf-8 -*-
"""T07 分集逻辑命令行示例入口。

用法（在 text2script/ 目录下）：
    python example_episodes.py --text "一句话创意：外卖小哥获得读心术"
    python example_episodes.py --file story.txt
    python example_episodes.py --file story.docx --format json
    python example_episodes.py --duration 60 --shots-per-minute 18 --file story.txt

支持 .txt 与 .docx（.docx 需要 python-docx，未安装时自动提示）。
"""

import argparse
import sys

import input_parser as ip
import episode_splitter as es

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
        import docx
    except ImportError:
        sys.exit("读取 .docx 需要 python-docx，请先安装：python -m pip install python-docx")
    document = docx.Document(path)
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="T07 分集逻辑示例")
    parser.add_argument("--text", help="直接传入故事文本")
    parser.add_argument("--file", help="读取故事文件（.txt / .docx）")
    parser.add_argument("--duration", type=int, default=es.DEFAULT_TARGET_DURATION,
                        help="集目标时长，60--90 秒（默认 75）")
    parser.add_argument("--shots-per-minute", type=int, default=es.SHOTS_PER_MINUTE,
                        help="分镜密度 18--22 镜/分钟（默认 20）")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="输出格式（默认 markdown）")
    args = parser.parse_args()

    if not args.text and not args.file:
        parser.error("请提供 --text 或 --file 之一")

    if args.text:
        raw = args.text
    else:
        path = args.file
        raw = read_docx_file(path) if path.lower().endswith(".docx") \
            else read_text_file(path)

    plan = es.split_episodes_from_text(
        raw,
        template=None,  # 本示例直接走规则引擎，不消费提示词模板
        target_duration=args.duration,
        shots_per_minute=args.shots_per_minute,
    )

    # 信息行走 stderr，保证 stdout 是纯内容（markdown / json），便于管道解析
    print(f"输入类型: {plan.input_type_label} ({plan.input_type})", file=sys.stderr)
    print(f"集数: {len(plan.episodes)}", file=sys.stderr)
    if plan.sensitive_hits:
        print(f"⚠ 命中红线类别: {'、'.join(plan.sensitive_hits)}（请人工确认后继续）",
              file=sys.stderr)
    if plan.warnings:
        print(f"生成提示: {'；'.join(plan.warnings)}", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    if args.format == "json":
        print(es.render_json(plan))
    else:
        print(es.render_markdown(plan, with_shots=True))


if __name__ == "__main__":
    main()