# -*- coding: utf-8 -*-
"""纯文转剧本单点工具统一入口（T17 工作流编排 + T18 错误处理）。

单次调用完整产出：T06 输入解析 -> T07 拆集 -> T08 角色关系 ->
T11-T15 分镜拆解。

用法（在 text2script/ 目录下）：
        python text2script.py --text "一句话创意：外卖小哥获得读心术"
        python text2script.py --file story.txt
        python text2script.py --file story.docx --format json
        python text2script.py --file story.txt --output out.md
        python text2script.py --text "粘贴或打字的任意故事" --format text --output out.txt
        python text2script.py --duration 60 --shots-per-minute 18 --file story.txt
        python text2script.py --version

    参数：
        --text                直接粘贴或打字传入故事文本（一句话/梗概/大纲/小说片段）
        --file                上传读取故事文件（.txt / .md / .docx）
        --duration            集目标时长，60--90 秒（默认 75）
        --shots-per-minute    分镜密度 18--22 镜/分钟（默认 20）
        --format markdown|json|text
                              输出格式（默认 markdown；text 为纯文字档，可直接粘贴）
        --output <path>       把结果写入文件；省略时输出到 stdout
        --version             打印版本号

    text 格式规则：
        - 纯文字档 / .txt，无表格装饰符号，减少不必要的标点
        - 超过 800 字时按「分镜节点」分段落（每个分镜一段，空行分隔）
        - ≤800 字紧凑连排，方便直接阅读

    stdout 只输出内容（markdown / json / text），信息行走 stderr，便于管道解析。
    .docx 需要 python-docx：python -m pip install python-docx。
    """

__version__ = "1.3.0"

import argparse
import os
import sys

import episode_splitter as es
import input_parser as ip
import storyboard as sb


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
    parser = argparse.ArgumentParser(
        description="纯文转剧本单点工具：文转剧本 + 分镜拆解",
        epilog="示例：python text2script.py --file story.txt --format json",
    )
    parser.add_argument("--version", action="version",
                        version=f"text2script {__version__}")
    parser.add_argument("--text", help="直接粘贴或打字传入故事文本（一句话/梗概/大纲/小说片段）")
    parser.add_argument("--file", help="读取故事文件（.txt / .md / .docx）")
    parser.add_argument("--duration", type=int, default=es.DEFAULT_TARGET_DURATION,
                        help="集目标时长，60--90 秒（默认 75）")
    parser.add_argument("--shots-per-minute", type=int, default=es.SHOTS_PER_MINUTE,
                        help="分镜密度 18--22 镜/分钟（默认 20）")
    parser.add_argument("--format", choices=["markdown", "json", "text"], default="markdown",
                        help="输出格式：markdown（默认）/ json / text（纯文字档 .txt）")
    parser.add_argument("--output", metavar="PATH",
                        help="把结果写入文件；省略时输出到 stdout")
    args = parser.parse_args()

    # T18 无输入兜底提示
    if not args.text and not args.file:
        parser.error("请提供 --text 或 --file 之一")

    if args.file:
        path = args.file
        if not os.path.exists(path):
            parser.error(f"文件不存在：{path}")
        try:
            raw = read_docx_file(path) if path.lower().endswith(".docx") \
                else read_text_file(path)
        except OSError as exc:
            sys.exit(f"读取文件失败：{exc}")

    if args.text:
        raw = args.text

    # T18 空输入兜底 + 长文本分段提示
    if not raw or not raw.strip():
        sys.exit("输入为空，请提供至少一段故事文本")
    parse = ip.parse_input(raw)
    if parse.chunk_count > 1:
        print(
            f"输入为长文本（清洗后约 {parse.cleaned_length} 字），"
            f"已按 {parse.chunk_count} 段切分处理",
            file=sys.stderr,
        )

    plan = sb.build_storyboard_plan(
        raw,
        template=None,  # 规则引擎直出，不消费提示词模板
        target_duration=args.duration,
        shots_per_minute=args.shots_per_minute,
    )

    # 信息行走 stderr，保证 stdout 是纯内容（markdown / json）
    print(f"输入类型: {plan.input_type_label} ({plan.input_type})", file=sys.stderr)
    print(f"集数: {len(plan.episodes)}", file=sys.stderr)
    if plan.sensitive_hits:
        print(f"⚠ 命中红线类别: {'、'.join(plan.sensitive_hits)}（请人工确认后继续）",
              file=sys.stderr)
    if plan.warnings:
        print(f"生成提示: {'；'.join(plan.warnings)}", file=sys.stderr)
    problems = sb.validate_storyboard(plan)
    if problems:
        print(f"分镜自检发现问题（{len(problems)}）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
    else:
        print("分镜自检通过：字段完整、枚举合法、密度/时长达标、转场不乱用",
              file=sys.stderr)

    if args.format == "json":
        content = sb.render_storyboard_json(plan)
    elif args.format == "text":
        # 超过 800 字：按分镜节点分段落（每个分镜一段，空行分隔）
        break_by_shot = parse.cleaned_length > 800
        content = sb.render_storyboard_text(plan, break_by_shot=break_by_shot)
        print(
            f"纯文字档输出：{parse.cleaned_length} 字"
            + ("，超过 800 字已按分镜节点分段落" if break_by_shot else "，紧凑连排"),
            file=sys.stderr,
        )
    else:
        content = sb.render_storyboard_markdown(plan)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(content + "\n")
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(content)
    print("=" * 64, file=sys.stderr)


if __name__ == "__main__":
    main()