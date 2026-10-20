# -*- coding: utf-8 -*-
"""T06 输入解析器：输入类型识别、文本清洗、超长分段、扩写判断、模板注入。

对应《纯文转剧本单点工具开发清单》T06 与 M0 规则定稿 T05（输入预处理规则）。
仅使用 Python 标准库，适配无 GUI 的 Linux 沙箱（Python 3.12）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ------------------- 默认参数（引用 M0-5） -------------------

ONE_LINE_MAX = 60        # 一句话创意：<=60 字且无段落结构
SUMMARY_MIN = 60         # 故事梗概：60~800 字且有情节线
SUMMARY_MAX = 800
CHUNK_SIZE = 2000        # 无章节标记时按约 2000 字切块
CHUNK_OVERLAP = 100      # 块间保留 100 字重叠以衔接上下文

# ------------------- 输入类型 -------------------

TYPE_ONE_LINE = "one_line"
TYPE_SUMMARY = "summary"
TYPE_EXCERPT = "excerpt"
TYPE_OUTLINE = "outline"

INPUT_TYPE_LABELS = {
    TYPE_ONE_LINE: "一句话创意",
    TYPE_SUMMARY: "故事梗概",
    TYPE_EXCERPT: "小说片段",
    TYPE_OUTLINE: "大纲/分卷",
}

# ------------------- 正则 -------------------

# 章节标题：行首的「第X卷/章/回」，支持中文数字与阿拉伯数字
CHAPTER_PATTERN = re.compile(
    r"^第[零一二三四五六七八九十百千万\d]+[卷章回][^\n]*", re.MULTILINE
)

# 对话段落：成对中文引号或英文引号包裹的短句
DIALOG_PATTERN = re.compile(r"[“\"]([^”\"\n]{1,80})[”\"]")

# 噪音行（封面/版权/目录/页码/网文水印）：仅当整行较短时删除，避免误伤正文
NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*封面\s*$"),
    re.compile(r"^\s*版权页?\s*$"),
    re.compile(r"^\s*目录\s*$"),
    re.compile(r"^\s*页眉\s*$"),
    re.compile(r"^\s*页脚\s*$"),
    re.compile(r"^\s*第\s*\d+\s*页\s*$"),
    re.compile(r"^\s*-\s*\d+\s*-\s*$"),
    re.compile(
        r"(天才一秒记住|一秒记住|最新章节|请收藏本站|手机用户请浏览|"
        r"阅读网址|上映时间|高清视频|未删减|www\.|\.com|\.net)",
        re.IGNORECASE,
    ),
]

# 标点统一映射（英文 -> 中文）
_PUNCT_MAP = {
    ",": "，",
    "?": "？",
    "!": "！",
    ";": "；",
    ":": "：",
    "(": "（",
    ")": "）",
}

# ------------------- 敏感红线清单（引用 M0-5：命中后提示确认，不自动删除） -------------------

SENSITIVE_RULES = {
    "血腥暴力": ["分尸", "碎尸", "肢解", "虐杀", "割喉", "血腥"],
    "低俗擦边": ["漏点", "情色", "艳照", "露骨", "性暗示"],
    "恐怖灵异": ["凶宅", "冤魂", "厉鬼", "降头", "诈尸"],
    "封建迷信": ["算命", "风水改运", "改运符", "血祭", "蛊术"],
    "侮辱群体": ["地域黑", "种族歧视", "职业歧视", "拜金"],
    "虚假宣传": ["包治百病", "稳赚不赔", "百分百升学", "放高利贷"],
    "真人肖像": ["真实人物", "明星写真", "肖像权"],
}

# ------------------- 数据结构 -------------------


@dataclass
class ParseResult:
    """一次输入解析的结果。"""

    input_type: str                 # 四类类型常量
    input_type_label: str           # 中文标签
    needs_expansion: bool           # 是否需要先扩写为剧本底稿
    cleaned_text: str               # 清洗后的文本
    chunks: List[str] = field(default_factory=list)   # 分段结果（保留语义切分）
    sensitive_hits: List[str] = field(default_factory=list)  # 命中的红线类别
    original_length: int = 0
    cleaned_length: int = 0
    chunk_count: int = 0
    rendered: List[str] = field(default_factory=list)  # 注入模板后的提示词列表


# ------------------- 清洗 -------------------


def _is_noise_line(line: str) -> bool:
    """判断是否为可安全删除的噪音行（封面/版权/目录/页码/网文水印）。"""
    s = line.strip()
    if not s:
        return False
    if len(s) > 40:
        return False  # 长行视为正文，不删
    return any(p.search(s) for p in NOISE_LINE_PATTERNS)


def _drop_toc(text: str) -> str:
    """删除「目录」标题及其后的目录条目区（到第一个章节标题为止）。

    目录条目通常紧跟在「目录」标题之后、正文第一个章节标题之前，
    删除该区间，保留正文章节标题供后续分段使用。
    """
    lines = text.split("\n")
    toc_idx = -1
    for i, line in enumerate(lines):
        if re.fullmatch(r"\s*目录\s*", line):
            toc_idx = i
            break
    if toc_idx == -1:
        return text

    first_chapter = None
    for j in range(toc_idx + 1, len(lines)):
        line = lines[j]
        # 跳过目录条目（章节标题 + 行尾页码，如「第一章 前夜 1」）
        if CHAPTER_PATTERN.search(line) and re.search(r"\d[ \t]*$", line.strip()):
            continue
        if CHAPTER_PATTERN.search(line):
            first_chapter = j
            break

    if first_chapter is None:
        # 无章节标题：保守只删除「目录」标题行
        del lines[toc_idx]
        return "\n".join(lines)
    return "\n".join(lines[:toc_idx] + lines[first_chapter:])


def unify_punctuation(s: str) -> str:
    """把英文标点统一为中文标点；小数点和英文缩写中的句点保留。

    引号统一为中文弯引号：“ / ”。英文双引号与中文直角引号「」均按
    开闭状态成对转换（M0-5 标点统一规则），保证下游台词识别一致。
    """
    out: List[str] = []
    quote_open = False
    corner_open = False
    for i, ch in enumerate(s):
        if ch == ".":
            prev_is_digit = bool(out and out[-1].isdigit())
            next_is_digit = i + 1 < len(s) and s[i + 1].isdigit()
            if prev_is_digit and next_is_digit:
                out.append(ch)  # 小数点，如 3.14
            else:
                out.append("。")
        elif ch == '"':
            if quote_open:
                out.append("”")
                quote_open = False
            else:
                out.append("“")
                quote_open = True
        elif ch == "「":
            if corner_open:
                out.append("”")  # 前一个「未闭合，容错为关闭
                corner_open = False
            else:
                out.append("“")
                corner_open = True
        elif ch == "」":
            out.append("”")
            corner_open = False
        else:
            out.append(_PUNCT_MAP.get(ch, ch))
    return "".join(out)


def clean_text(text: str) -> str:
    """清洗输入文本：删目录区与噪音行、去全角空格、统一标点、折叠空行。"""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _drop_toc(text)

    kept: List[str] = []
    for line in text.split("\n"):
        if _is_noise_line(line):
            continue
        kept.append(unify_punctuation(line.rstrip()))

    joined = "\n".join(kept)
    # 折叠连续空行（最多保留一个）
    joined = re.sub(r"\n[ \t]*\n([ \t]*\n)+", "\n\n", joined)
    # 移除全角空格
    joined = joined.replace("\u3000", "")
    return joined.strip()


# ------------------- 类型识别 -------------------


def _has_dialogue(text: str) -> bool:
    """是否含成对引号包裹的对话段落。"""
    return bool(DIALOG_PATTERN.search(text))


def detect_input_type(text: str) -> str:
    """识别输入类型：大纲/分卷 > 一句话创意 > 小说片段 > 故事梗概。

    判定依据 M0-5：一句话<=60字且无段落结构；梗概60~800字有情节线；
    小说片段>800字或含对话段落；大纲含「第X卷/章」标题。
    """
    clean = text.strip()
    if not clean:
        raise ValueError("输入为空，请提供故事素材")

    if CHAPTER_PATTERN.search(clean):
        return TYPE_OUTLINE

    if len(clean) <= ONE_LINE_MAX and "\n" not in clean:
        return TYPE_ONE_LINE

    if len(clean) > SUMMARY_MAX or _has_dialogue(clean):
        return TYPE_EXCERPT

    return TYPE_SUMMARY


def needs_expansion(input_type: str) -> bool:
    """是否需先扩写为剧本底稿：仅一句话创意需要。"""
    return input_type == TYPE_ONE_LINE


# ------------------- 分段 -------------------


def split_by_chapter(text: str) -> List[str]:
    """按章节标题切分文本；无标题时返回空列表。"""
    matches = list(CHAPTER_PATTERN.finditer(text))
    if not matches:
        return []

    chunks: List[str] = []
    prev = 0
    for m in matches:
        if m.start() > prev:
            head = text[prev:m.start()].strip()
            if head:
                chunks.append(head)
        prev = m.start()
    tail = text[prev:].strip()
    if tail:
        chunks.append(tail)
    return [c for c in chunks if c]


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """按约 chunk_size 切块，块间保留 overlap 字重叠；尽量在句号/段落边界切。"""
    chunks: List[str] = []
    start = 0
    n = len(text)
    if n <= chunk_size:
        return [text.strip()] if text.strip() else []

    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = text[start:end]
            cut = max(
                window.rfind("\n\n"),
                window.rfind("。"),
                window.rfind("！"),
                window.rfind("？"),
                window.rfind("；"),
            )
            if cut > chunk_size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


def split_long_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """超长文本分段：优先按章节标记切分；无章节时按约 2000 字切块并保留 100 字重叠。"""
    text = text.strip()
    if not text:
        return []

    chapters = split_by_chapter(text)
    if chapters:
        result: List[str] = []
        for ch in chapters:
            if len(ch) <= chunk_size:
                result.append(ch)
            else:
                result.extend(_chunk_text(ch, chunk_size, overlap))
        return result

    return _chunk_text(text, chunk_size, overlap)


# ------------------- 敏感拦截（不删除，仅提示确认） -------------------


def check_sensitive(text: str) -> List[str]:
    """检查敏感红线，返回命中的规则类别名列表（空列表表示未命中）。"""
    hits: List[str] = []
    for category, keywords in SENSITIVE_RULES.items():
        if any(kw in text for kw in keywords):
            hits.append(category)
    return hits


# ------------------- 模板注入 -------------------

PLACEHOLDER_INPUT = "{输入原文}"


def inject_prompt(template: str, text: str) -> str:
    """把 {输入原文} 占位符替换为实际文本；无占位符时原样返回模板。"""
    if PLACEHOLDER_INPUT not in template:
        return template
    return template.replace(PLACEHOLDER_INPUT, text)


# ------------------- 总入口 -------------------


def parse_input(
    raw_text: str,
    template: Optional[str] = None,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> ParseResult:
    """输入解析主流程：清洗 -> 类型识别 -> 扩写判断 -> 分段 -> 敏感检查 -> 模板注入。"""
    cleaned = clean_text(raw_text)
    input_type = detect_input_type(cleaned)
    chunks = split_long_text(cleaned, chunk_size, overlap)
    hits = check_sensitive(cleaned)

    result = ParseResult(
        input_type=input_type,
        input_type_label=INPUT_TYPE_LABELS[input_type],
        needs_expansion=needs_expansion(input_type),
        cleaned_text=cleaned,
        chunks=chunks,
        sensitive_hits=hits,
        original_length=len(raw_text or ""),
        cleaned_length=len(cleaned),
        chunk_count=len(chunks),
    )

    if template:
        result.rendered = [inject_prompt(template, c) for c in chunks]
    return result