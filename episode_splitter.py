# -*- coding: utf-8 -*-
"""T07 分集逻辑：强钩子拆集引擎。

对应《纯文转剧本单点工具开发清单》T07 与 M0 规则定稿 T03（提示词模板 V1）：
按 60--90 秒/集拆集，自动生成集序与集间衔接；每集只讲一个核心冲突，
集末必出悬念/反转/危机/新信息；台词口语化、单句不超过 35 字；
输出遵循 T01 剧本格式字段，并附带符合 T02 约束的分镜草稿。
仅使用 Python 标准库，适配无 GUI 的 Linux 沙箱（Python 3.12）。

衔接：本模块消费 T06 输入解析器（input_parser.py）的 ParseResult；
后续由 T08 深化角色关系线、T09 深化集末钩子、T10 负责剧本导出。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

import input_parser as ip

# ------------------- 默认参数（引用 M0-1 / T03 V1 / T02） -------------------

DEFAULT_TARGET_DURATION = 75          # 集目标时长（60--90 秒）
SHOTS_PER_MINUTE = 20                 # 分镜密度（18--22 镜/分钟）
SHOT_MIN_DURATION = 2                 # 单镜建议时长下限（秒）
SHOT_MAX_DURATION = 5                 # 单镜建议时长上限（秒）
LINE_MAX_LENGTH = 35                  # 台词单句上限（字）
CONFLICT_MIN_LENGTH = 5               # 核心冲突最短字数
HOOK_MIN_LENGTH = 5                   # 集末钩子最短字数

# 枚举（引用 T01/T02 定稿）
SHOT_SIZES = ["远景", "全景", "中景", "近景", "特写"]
CAMERAS = ["固定", "推", "拉", "摇", "移", "跟随"]
SCENE_TIMES = ["清晨", "日", "黄昏", "夜"]
CHARACTER_ROLES = ["主角", "配角", "反派"]
HOOK_TYPES = ["悬念", "反转", "危机", "新信息"]

# 英文枚举（输入英文 -> 输出英文时使用）
SHOT_SIZES_EN = ["Wide", "Full", "Medium", "Close-up", "Extreme Close-up"]
CAMERAS_EN = ["Static", "Push in", "Pull back", "Pan", "Tilt", "Track"]
SCENE_TIMES_EN = ["Dawn", "Day", "Dusk", "Night"]
CHARACTER_ROLES_EN = ["Protagonist", "Supporting", "Antagonist"]
HOOK_TYPES_EN = ["Suspense", "Twist", "Crisis", "New Info"]

# 情绪-表情-音调词典（初始版，引用 M0-4 T04；后续 T14 做完整映射）
EMOTION_DICT = {
    "平静": ("神情如常", "平稳"),
    "愤怒": ("眉头紧锁、咬牙", "高亢急促"),
    "悲伤": ("眼眶泛红、垂眼", "低沉断续"),
    "惊讶": ("瞳孔放大、嘴微张", "上扬短促"),
    "恐惧": ("面色发白、后退", "颤抖压低"),
    "喜悦": ("嘴角上扬、眼睛弯起", "轻快明亮"),
    "冷漠": ("面无表情、视线平直", "平稳无起伏"),
    "紧张": ("嘴唇抿紧、眼神游移", "轻微发颤"),
    "得意": ("微抬下巴、嘴角带笑", "慢而从容"),
    "专注": ("目光凝住、身体前倾", "平稳"),
    "迟疑": ("眼神闪躲、动作停顿", "迟疑低压"),
}

# 英文情绪-表情-音调词典
EMOTION_DICT_EN = {
    "Calm": ("expression normal", "steady"),
    "Angry": ("brow furrowed, jaw clenched", "sharp and fast"),
    "Sad": ("eyes reddening, gaze lowered", "low and broken"),
    "Surprised": ("pupils dilated, mouth slightly open", "rising and short"),
    "Afraid": ("face paling, stepping back", "trembling and hushed"),
    "Happy": ("corners of mouth up, eyes curved", "light and bright"),
    "Indifferent": ("expressionless, flat gaze", "steady and flat"),
    "Tense": ("lips pressed, eyes shifting", "slightly trembling"),
    "Proud": ("chin raised, faint smile", "slow and unhurried"),
    "Focused": ("eyes fixed, body leaning in", "steady"),
    "Hesitant": ("eyes darting, movement paused", "hesitant and low"),
}

# 英文台词长度按词数计（中文按字数 35 字；英文 35 字符太短）
LINE_MAX_WORDS = 35

# 冲突线索词（用于从素材中定位"核心冲突"句）
_CONFLICT_KEYWORDS = [
    "却", "但", "竟然", "居然", "没想到", "忽然", "突然", "背叛", "发现",
    "威胁", "夺", "抢", "杀", "仇", "恨", "暴露", "真相", "秘密", "失败",
    "输", "反目", "失踪", "危机", "逼", "骗", "误会", "离开", "放弃",
]

# 英文冲突线索词（英文模式核心冲突句定位）
_EN_CONFLICT_KEYWORDS = [
    "but", "however", "yet", "suddenly", "unexpectedly", "all of a sudden",
    "discover", "discovered", "secret", "mystery", "truth", "betray",
    "betrayed", "threat", "danger", "kill", "killed", "save", "rescue",
    "escape", "trap", "conspiracy", "plot", "fail", "failed", "lost",
    "lose", "revenge", "enemy", "attack", "chase", "hidden", "reveal",
    "revealed", "turns out", "in danger",
]

# 反派线索词（用于识别反派角色）
_VILLAIN_KEYWORDS = ["反派", "敌人", "仇家", "杀手", "对头", "宿敌", "幕后"]

# 英文反派线索词（识别反派角色，英文模式）
_EN_VILLAIN_KEYWORDS = [
    "villain", "enemy", "antagonist", "killer", "assassin", "rival",
    "thug", "boss", "gangster", "hunter",
]

# 名词角色标记：说话人提取
_SPEAKER_PATTERNS = [
    re.compile(r"【([^】]{1,8})】(?:（.*?）)?[“\"]([^“”\"\n]{1,120})[”\"]"),
    re.compile(
        r"([\u4e00-\u9fa5]{2,3}?)(?:说道|问道|喊道|低语|回答|冷笑|苦笑|"
        r"怒道|喝道|沉声道|厉声道|说|问|道(?=[：:，。！“”]))"
    ),
]

# 说话动词表（台词归属用，顺序：长词优先，避免「问道」被拆成「问+道」）
_SPEECH_VERBS = (
    "说道", "问道", "喊道", "低语", "回答", "冷笑", "苦笑", "怒道",
    "喝道", "沉声道", "厉声道", "说", "问",
)
_SPEAKER_STRIP_RE = re.compile(r"(?:{})$".format("|".join(_SPEECH_VERBS)))

# 地点线索词（场景提取；要求「在/来到…」后紧跟标点或句末，避免吞入动词）
_LOCATION_PATTERNS = [
    re.compile(r"(?:来到|走进|回到|出现在)([\u4e00-\u9fa5]{2,8})(?:的)?(?=[，。；！？\n]|$)")
    ,
    re.compile(r"在([\u4e00-\u9fa5]{2,8})(?:的)?(?=[，。；！？\n]|$)"),
    re.compile(
        r"([\u4e00-\u9fa5]{0,6}?(?:办公室|房间|客厅|街道|森林|医院|学校|工厂|"
        r"仓库|酒吧|餐厅|天台|楼道|警局|广场|别墅|小区|码头|战场)"
        r"(?:里|内|外|上|下|中|旁)?)(?=[，。；！？\n]|$)"
    ),
]

# 非人名的说话前缀过滤（角色提取用）：常见语气/动作/疑问词
_NON_NAME_SUFFIXES = (
    "急切", "低声", "冷静", "愤怒", "严肃", "轻声", "厉声", "淡淡", "冷冷",
    "深深", "微微", "缓缓", "忽然", "突然", "认真", "诚恳", "激动", "紧张",
    "小心", "好奇", "疑惑", "惊讶", "坚定", "果断", "犹豫", "尴尬", "高兴",
    "得意", "无奈", "抱歉", "自信", "温柔", "轻柔", "大声", "小声", "皱眉",
    "冷笑", "叹息", "摇头", "点头", "沉声", "追问", "大声", "喃喃",
)
_NON_NAME_STOPWORDS = (
    "怎么", "什么", "这个", "那个", "为何", "哪里", "难道", "不会",
    "还是", "忽然", "突然", "急切", "低声", "皱眉",
)

# 群体/场景词（引号后置提取时易误当说话人，如「。满堂宾客的目光」）
_NON_NAME_GROUP_WORDS = (
    "满堂", "全场", "众人", "人群", "观众", "宾客", "弹幕", "直播间",
    "大家", "诸位", "所有人", "全城", "全校", "满屋", "满座",
)

# 说话动作/表情后缀（冒号前置、引号后置说话人识别用；长词优先）
_ACTION_SUFFIXES = (
    "咧嘴一笑", "压低声音", "深吸一口气", "脸色煞白", "笑了笑",
    "淡淡一笑", "冷笑一声", "苦笑一声", "嗤笑一声",
    "冷笑", "苦笑", "嗤笑", "咬牙", "顿了顿", "站起身", "皱眉", "抬头",
)
_ACTION_ALTERNATION = "|".join(_ACTION_SUFFIXES)

# 说话人短语识别（T23 修复 F2）：冒号前置「XX动作：(台词)」、引号后置「(台词)」XX动作
_SPEAKER_PHRASE_PATTERNS = [
    re.compile(
        r"([\u4e00-\u9fa5]{2,3}?(?:" + _ACTION_ALTERNATION + r"))[：:][“\"]"
    ),
    re.compile(
        r"[”\"][，。！？…\s]{0,2}"
        r"([\u4e00-\u9fa5]{2,3}?(?:" + _ACTION_ALTERNATION + r")?)"
    ),
]


def _looks_like_name(candidate: str) -> bool:
    """判断候选说话人是否像人名（过滤副词/疑问/表情修饰词/代词开头/群体词）。"""
    if not candidate or len(candidate) > 3:
        return False
    if candidate in _NON_NAME_GROUP_WORDS:
        return False  # 群体/场景词不视为角色名（如「满堂」「弹幕」）
    if candidate[0] in "他她我你":
        return False  # 代词开头的短语不视为角色名（如「他说」「她转身」）
    if any(w in candidate for w in _NON_NAME_STOPWORDS):
        return False
    if candidate.endswith(_NON_NAME_SUFFIXES):
        return False
    return True

_TIME_KEYWORDS = {
    "清晨": ["清晨", "天亮", "破晓"],
    "日": ["白天", "日光", "日头", "正午"],
    "黄昏": ["黄昏", "傍晚", "夕阳"],
    "夜": ["夜晚", "深夜", "夜里", "午夜", "晚上", "夜色"],
}

# 英文时间关键词（英文模式场景时间；顺序即优先级）
_EN_TIME_KEYWORDS = {
    "Dawn": ["dawn", "sunrise", "early morning", "morning"],
    "Dusk": ["dusk", "twilight", "sunset", "evening"],
    "Night": ["night", "midnight", "late night"],
    "Day": ["noon", "daytime", "afternoon", "day"],
}

# 英文地点关键词（英文模式场景地点；命中即取该句为场景）
_EN_LOCATION_KEYWORDS = (
    "office", "room", "house", "home", "apartment", "street", "road",
    "alley", "forest", "woods", "hospital", "school", "factory",
    "warehouse", "bar", "restaurant", "cafe", "coffee", "rooftop",
    "hallway", "corridor", "station", "airport", "plaza", "square",
    "villa", "pier", "dock", "battlefield", "city", "town", "village",
    "shop", "store", "park", "river", "bridge", "hotel", "library",
    "train", "car", "club", "basement", "cave", "temple",
)

# 英文说话动词（英文模式台词归属：先长词后短词）
_EN_SPEECH_VERBS = (
    "whispered", "shouted", "answered", "replied", "murmured", "demanded",
    "snapped", "yelled", "sighed", "muttered", "screamed", "called",
    "said", "asked",
)

# 英文人名提取时忽略的句首大写词（代词/冠词/连词等）
_EN_NAME_STOP = {
    "He", "She", "It", "They", "The", "A", "An", "And", "But", "Then",
    "His", "Her", "This", "That", "These", "Those", "We", "I", "You",
    "There", "Here", "Now", "When", "What", "Who", "How", "Why", "Where",
}

# 英文引号内台词提取
_EN_QUOTE_RE = re.compile(r"\"([^\"\n]{1,300})\"")


# ------------------- 数据结构（T01 剧本字段 + T02 分镜草稿） -------------------


@dataclass
class Scene:
    id: int
    location: str
    time: str
    setting: str


@dataclass
class Character:
    name: str
    role: str                    # 主角/配角/反派
    description: str


@dataclass
class Line:
    speaker: str                 # 角色名或"旁白"
    tone: str                    # 语气
    text: str                    # 台词/旁白内容（单句 <= 35 字）


@dataclass
class Shot:
    shot: int                    # 镜号，每集从 1 开始
    shot_size: str               # 景别（枚举）
    camera: str                  # 运镜（枚举）
    visual: str                  # 画面内容（含动作与位置）
    dialogue: Optional[str]      # 台词/旁白，可空
    character: str               # 出场角色
    emotion: str                 # 情绪（词典）
    expression: str              # 表情（词典）
    tone: str                    # 音调（词典）
    duration: int                # 建议时长（2--5 秒）


@dataclass
class Episode:
    episode: int                 # 集序，从 1 开始
    target_duration: int         # 目标时长（60--90 秒）
    core_conflict: str           # 核心冲突（一集一个）
    episode_hook: str            # 集末钩子（悬念/反转/危机/新信息）
    hook_type: str               # 钩子类型（枚举）
    scenes: List[Scene] = field(default_factory=list)
    characters: List[Character] = field(default_factory=list)
    lines: List[Line] = field(default_factory=list)
    shots: List[Shot] = field(default_factory=list)
    continuity: str = ""         # 集间衔接（第 1 集为空，后续集写承接上集钩子）
    warnings: List[str] = field(default_factory=list)   # 规则未覆盖时的提示
    source_text: str = ""        # 本集原始素材文本（T08 角色关系线增强输入）
    relations: List[dict] = field(default_factory=list) # 角色关系线（T08 填充）
    language: str = "zh"         # 输出语言：zh / en


@dataclass
class EpisodePlan:
    episodes: List[Episode] = field(default_factory=list)
    input_type: str = ""
    input_type_label: str = ""
    needs_expansion: bool = False
    sensitive_hits: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    language: str = "zh"             # 输入语言：zh（中文）/ en（英文）


# ------------------- 文本工具 -------------------


def _split_sentences(text: str) -> List[str]:
    """按句末标点切句，保留标点；清理切句产生的首尾引号残留。"""
    parts = re.split(r"(?<=[。！？；])", text.replace("\n", "。"))
    out: List[str] = []
    for p in parts:
        p = p.strip().strip("“”\"'")
        if p:
            out.append(p)
    return out


def _split_sentences_lang(text: Optional[str], language: str = "zh") -> List[str]:
    """按语言切句：中文按「。！？；」；英文按句点/问号/感叹号后随空格或行尾。"""
    if not text:
        return []
    if language == "en":
        parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        out: List[str] = []
        for p in parts:
            p = p.strip().strip("\"'")
            if p:
                out.append(p)
        # 无标点整段兜底
        if not out and text.strip():
            out = [text.strip().strip("\"'")]
        return out
    return _split_sentences(text)


def clip_by_words(text: str, max_words: int = LINE_MAX_WORDS) -> str:
    """把英文台词/旁白压缩到 <= max_words 词，优先在句末标点处截断。"""
    text = text.strip()
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    head = words[:max_words]
    cut = -1
    for i in range(len(head) - 1, -1, -1):
        if head[i].endswith((".", "!", "?")):
            cut = i
            break
    if cut >= 5:
        return " ".join(head[: cut + 1])
    return " ".join(head) + "…"


def clip_line(text: str, max_len: int = LINE_MAX_LENGTH) -> str:
    """把台词/旁白压缩到 <= max_len 字：优先在标点处截断，避免硬切。"""
    text = text.strip()
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    window = text[:max_len]
    cut_at = max(window.rfind("。"), window.rfind("！"),
                 window.rfind("？"), window.rfind("，"),
                 window.rfind("；"), window.rfind("："))
    if cut_at >= 10:
        return window[: cut_at + 1]
    return window[: max_len - 1] + "…"


def _normalize_time(text: str) -> str:
    for time_key, words in _TIME_KEYWORDS.items():
        if any(w in text for w in words):
            return time_key
    return "日"


def _extract_location(text: str) -> str:
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text)
        if m:
            loc = m.group(1).strip()
            if loc:
                return loc
    return "未注明地点"


def _normalize_time_en(text: str) -> str:
    """英文模式：时段关键词归一化；默认 Day。"""
    lower = text.lower()
    for time_key, words in _EN_TIME_KEYWORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", lower):
                return time_key
    return "Day"


def _extract_location_en(text: str) -> str:
    """英文模式：地点关键词命中即取该词为地点（首字母大写）。"""
    lower = text.lower()
    for kw in _EN_LOCATION_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return kw.title()
    return ""


def _extract_scenes_en(text: str) -> List[Scene]:
    """英文模式提取场景：地点关键词 + 时段枚举；无法识别时给默认场景。"""
    sentences = _split_sentences_lang(text, "en")
    scenes: List[Scene] = []
    seen: set = set()
    for sent in sentences:
        loc = _extract_location_en(sent)
        if loc and loc not in seen:
            seen.add(loc)
            scenes.append(
                Scene(
                    id=len(scenes) + 1,
                    location=loc,
                    time=_normalize_time_en(sent),
                    setting=clip_by_words(sent, 12),
                )
            )
    if not scenes:
        scenes.append(
            Scene(id=1, location="Unnamed Location",
                  time=_normalize_time_en(text),
                  setting=clip_by_words(text, 12) or "Main storyline setting")
        )
    return scenes


def _extract_scenes(text: str) -> List[Scene]:
    """提取场景：地点 + 时间枚举；无法识别时给默认场景。"""
    sentences = _split_sentences(text)
    scenes: List[Scene] = []
    seen: set = set()
    for sent in sentences:
        loc = _extract_location(sent)
        if loc != "未注明地点" and loc not in seen:
            seen.add(loc)
            scenes.append(
                Scene(
                    id=len(scenes) + 1,
                    location=loc,
                    time=_normalize_time(sent),
                    setting=sent[:40],
                )
            )
    if not scenes:
        scenes.append(
            Scene(id=1, location="未注明地点", time=_normalize_time(text),
                  setting=text[:40] or "剧情主要场景")
        )
    return scenes


def _strip_action_suffix(name: str) -> str:
    """剥离说话动作/表情后缀（如「阿凯压低声音」->「阿凯」）。"""
    for suf in _ACTION_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def _extract_characters(text: str) -> List[Character]:
    """初步角色提取（T07 基础版；关系线深化在 T08）。

    规则：说话人标记【X】/「X说」/冒号前置「XX动作：(台词)」/
    引号后置「(台词)」XX动作 出现频次排序；最高频为主角，次高频为配角；
    含反派线索词的句子关联的名字标记为反派。
    """
    freq: dict = {}
    for pat in _SPEAKER_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).strip()
            if name and name != "旁白" and len(name) <= 8 \
                    and _looks_like_name(name):
                freq[name] = freq.get(name, 0) + 1

    for pat in _SPEAKER_PHRASE_PATTERNS:
        for m in pat.finditer(text):
            name = _strip_action_suffix(m.group(1).strip())
            if name and name != "旁白" and len(name) <= 8 \
                    and _looks_like_name(name):
                freq[name] = freq.get(name, 0) + 1

    if not freq:
        # 无明确说话人：正文主语无法确定，放占位并留待 T08 深化
        return [Character(name="主角", role="主角", description="线索推动者（待 T08 深化）")]

    ordered = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    chars: List[Character] = []
    villain_names: set = set()
    # 反派判定只看叙述句（过滤引号内对话），避免「提到仇家的人」被误标反派
    narration = re.sub(r"[“\"][^“”\"\n]{1,120}[”\"]", "", text)
    for sent in _split_sentences(narration):
        if any(kw in sent for kw in _VILLAIN_KEYWORDS):
            for name, _ in ordered:
                if name in sent:
                    villain_names.add(name)

    for i, (name, _cnt) in enumerate(ordered[:3]):
        if name in villain_names:
            role = "反派"
            desc = "冲突制造者"
        elif i == 0:
            role = "主角"
            desc = "线索推动者"
        else:
            role = "配角"
            desc = "剧情对照者"
        chars.append(Character(name=name, role=role, description=desc))
    return chars


def _looks_like_name_en(name: str) -> bool:
    """英文模式：像人名的词（首字母大写、不含停用词）。"""
    return bool(name) and len(name) <= 20 \
        and re.fullmatch(r"[A-Z][A-Za-z'\-]*", name) \
        and name not in _EN_NAME_STOP


def _extract_characters_en(text: str) -> List[Character]:
    """英文模式初步角色提取。

    规则：引号后置/前置的「said X / X said / X asked:」结构识别说话人；
    「said」等动词后无引号时也尝试；频次最高为主角，次高为配角；
    叙述句含反派线索词时关联的名字标记为反派。
    """
    verbs = "|".join(_EN_SPEECH_VERBS)
    freq: dict = {}
    for m in _EN_QUOTE_RE.finditer(text):
        pre = text[max(0, m.start() - 30):m.start()]
        post = text[m.end():m.end() + 30]
        hits = [
            re.search(r"([A-Z][A-Za-z'\-]{1,15})\s+(?:" + verbs + r")\s*[:]?\s*$", pre),
            re.search(r"^\s*(?:" + verbs + r")\s+([A-Z][A-Za-z'\-]{1,15})", post),
            re.search(r"^\s*([A-Z][A-Za-z'\-]{1,15})\s+(?:" + verbs + r")", post),
            re.search(r"([A-Z][A-Za-z'\-]{1,15})\s+(?:" + verbs + r")\s*$", pre),
            re.search(r"([A-Z][A-Za-z'\-]{1,15})(?:\s+\w+){0,4}\s+(?:"
                      + verbs + r")\s*[:]?\s*$", pre),
        ]
        for mh in hits:
            if mh:
                name = mh.group(1).strip()
                if _looks_like_name_en(name):
                    freq[name] = freq.get(name, 0) + 1
                break

    if not freq:
        return [Character(name="Protagonist", role="Protagonist",
                          description="Plot driver (to be refined)")]

    ordered = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    chars: List[Character] = []
    villain_names: set = set()
    narration = re.sub(r"\"[^\"\n]{1,300}\"", "", text)
    for sent in _split_sentences_lang(narration, "en"):
        lower = sent.lower()
        if any(re.search(rf"\b{re.escape(kw)}\b", lower)
               for kw in _EN_VILLAIN_KEYWORDS):
            for name, _ in ordered:
                if re.search(rf"\b{re.escape(name)}\b", sent):
                    villain_names.add(name)

    for i, (name, _cnt) in enumerate(ordered[:3]):
        if name in villain_names:
            role, desc = "Antagonist", "Conflict creator"
        elif i == 0:
            role, desc = "Protagonist", "Plot driver"
        else:
            role, desc = "Supporting", "Counterpart"
        chars.append(Character(name=name, role=role, description=desc))
    return chars


def _infer_quote_speaker_en(text: str, m: re.Match,
                            known_names: List[str]) -> Optional[str]:
    """英文模式：从引号句前后文推断说话人。

    优先级：后文「said X / X said」> 前文「X said / X said:」。
    仅在窗口内出现已知角色名时归属，否则返回 None（由调用方归 Narrator）。
    """
    if not known_names:
        return None
    names = sorted(known_names, key=len, reverse=True)
    pre = text[max(0, m.start() - 30):m.start()]
    post = text[m.end():m.end() + 30]
    verbs = "|".join(_EN_SPEECH_VERBS)
    for n in names:
        if n == "Narrator":
            continue
        pattern = r"\b" + re.escape(n) + r"\b"
        if re.search(r"(?:" + verbs + r")\s+" + pattern, post, re.IGNORECASE):
            return n
        if re.search(pattern + r"\s+(?:" + verbs + r")", post, re.IGNORECASE):
            return n
        if re.search(pattern + r"\s+(?:" + verbs + r")\s*[:]?\s*$",
                     pre, re.IGNORECASE):
            return n
        if re.search(pattern + r"(?:\s+\w+){0,4}\s+(?:" + verbs
                     + r")\s*[:]?\s*$", pre, re.IGNORECASE):
            return n
        if ":" in pre:
            head = re.split(r"[:]", pre)[-1]
            if re.search(pattern, head, re.IGNORECASE):
                return n
    return None


def _extract_lines_en(text: str,
                      known_names: Optional[List[str]] = None) -> List[Line]:
    """英文模式提取台词与旁白：说话人 + 语气 + 文本；文本 <=35 词。

    规则：优先双引号句；按后文/前文说话动词归属已知角色，
    无明确说话人归 Narrator；无引号时把开头叙事句提炼为旁白。
    """
    known_names = known_names or []
    lines: List[Line] = []
    used: set = set()

    for m in _EN_QUOTE_RE.finditer(text):
        content = m.group(1).strip()
        if not content:
            continue
        clipped = clip_by_words(content, LINE_MAX_WORDS)
        if not clipped:
            continue
        if any(ln.text == clipped for ln in lines):
            continue
        speaker = _infer_quote_speaker_en(text, m, known_names)
        if speaker and (speaker, clipped) not in used:
            used.add((speaker, clipped))
            lines.append(Line(speaker=speaker, tone="steady", text=clipped))
            continue
        lines.append(Line(speaker="Narrator", tone="steady", text=clipped))

    if not lines:
        narr = _split_sentences_lang(text, "en")
        if narr:
            clipped = clip_by_words(narr[0], LINE_MAX_WORDS)
            if clipped:
                lines.append(Line(speaker="Narrator", tone="steady",
                                  text=clipped))
    return lines


def _extract_core_conflict_en(text: str) -> Tuple[str, List[str]]:
    """英文模式定位核心冲突句：冲突线索词 > 情绪/疑问句 > 首句。"""
    sents = _split_sentences_lang(text, "en")
    if not sents:
        return "", ["No sentences found in the source text; expand the draft first"]

    for sent in sents:
        lower = sent.lower()
        if any(re.search(rf"\b{re.escape(kw)}\b", lower)
               for kw in _EN_CONFLICT_KEYWORDS):
            return clip_by_words(sent, 40), []

    for sent in sents:
        if sent.rstrip().endswith(("?", "!")) or any(
            w in sent.lower()
            for w in ["angry", "shock", "fear", "afraid", "cry", "shout",
                      "hate", "despair", "panic"]
        ):
            return clip_by_words(sent, 40), []

    warn = ["No obvious conflict sentence found; first sentence used as "
            "core conflict, please review"]
    return clip_by_words(sents[0], 40), warn


def _infer_quote_speaker(text: str, m: re.Match,
                         known_names: List[str]) -> Optional[str]:
    """从引号句前后文推断说话人（T23 修复 F2）。

    优先级：冒号前置「XX动作：(台词)」 > 引号后置「(台词)」XX动作…。
    仅在窗口内出现已知角色名时归属，否则返回 None（由调用方归旁白）。
    """
    if not known_names:
        return None
    names = sorted(known_names, key=len, reverse=True)
    pre = text[max(0, m.start() - 16):m.start()]
    post = text[m.end():m.end() + 12]
    # 1) 冒号前置：冒号前 16 字内命中已知角色名
    if "：" in pre or ":" in pre:
        head = re.split(r"[：:]", pre)[0]
        for n in names:
            if n and n != "旁白" and n in head:
                return n
    # 2) 引号后置：引号闭合后 12 字内命中已知角色名
    for n in names:
        if n and n != "旁白" and n in post:
            return n
    return None


def _extract_lines(text: str, known_names: Optional[List[str]] = None,
                   ) -> List[Line]:
    """提取台词与旁白：说话人 + 语气 + 文本；文本强制压缩到 <=35 字。

    规则：优先匹配【说话人】（语气：XX）"台词"；其次「已知角色名说/道/问：」；
    再其次引号句按冒号前置/引号后置的已知说话人归属，无明确说话人归旁白；
    无引号时把开头叙事句提炼为旁白，保证每集至少 1 行台词。
    """
    known_names = known_names or []
    lines: List[Line] = []
    used: set = set()

    # 1. 【说话人】（语气：XX）"台词"
    pat1 = re.compile(
        r"【([^】]{1,8})】(?:（语气[:：]?([^）]{1,8})）)?[“\"]([^“”\"\n]{1,120})[”\"]"
    )
    for m in pat1.finditer(text):
        speaker, tone, content = m.group(1), m.group(2) or "平稳", m.group(3)
        clipped = clip_line(content)
        if clipped and (speaker, clipped) not in used:
            used.add((speaker, clipped))
            lines.append(Line(speaker=speaker, tone=tone.strip() or "平稳",
                              text=clipped))

    def _known_speaker(phrase: str) -> Optional[str]:
        """从「X说/道/问：」短语中剥离动词，识别已知角色名。"""
        name = _SPEAKER_STRIP_RE.sub("", phrase)
        name = name.strip()
        if name in known_names:
            return name
        return None

    # 2. 「角色名说：」结构；无已知角色归属时走旁白
    pat2 = re.compile(
        "([\u4e00-\u9fa5]{2,4}(?:" + "|".join(_SPEECH_VERBS) + "))"
        "[：:][“\"]([^“”\"\n]{1,120})[”\"]"
    )
    for m in pat2.finditer(text):
        content = m.group(2).strip()
        if not content:
            continue
        clipped = clip_line(content)
        if not clipped or (m.group(1), clipped) in used:
            continue
        speaker = _known_speaker(m.group(1))
        if speaker:
            used.add((speaker, clipped))
            lines.append(Line(speaker=speaker, tone="平稳", text=clipped))

    # 3. 其余引号句：优先归属已知说话人（冒号前置 > 引号后置），否则旁白
    for m in re.finditer(r"[“\"]([^“”\"\n]{2,120})[”\"]", text):
        content = m.group(1).strip()
        if not content:
            continue
        clipped = clip_line(content)
        if not clipped:
            continue
        dup = any(ln.text == clipped for ln in lines)
        if dup:
            continue
        speaker = _infer_quote_speaker(text, m, known_names)
        if speaker and (speaker, clipped) not in used:
            used.add((speaker, clipped))
            lines.append(Line(speaker=speaker, tone="平稳", text=clipped))
            continue
        lines.append(Line(speaker="旁白", tone="平稳", text=clipped))

    # 4. 无台词时：提炼叙事首句为旁白
    if not lines:
        narr = _split_sentences(text)
        if narr:
            clipped = clip_line(narr[0])
            if clipped:
                lines.append(Line(speaker="旁白", tone="平稳", text=clipped))
    return lines


def _extract_core_conflict(text: str) -> Tuple[str, List[str]]:
    """定位核心冲突句：优先含冲突线索词的句子，其次情绪/疑问句，再取首句。

    返回 (冲突文本, 警告列表)。
    """
    sents = _split_sentences(text)
    if not sents:
        return "", ["素材无可切分句子，建议先扩写剧本底稿"]

    for sent in sents:
        if any(kw in sent for kw in _CONFLICT_KEYWORDS):
            return clip_line(sent, 60), []

    for sent in sents:
        if sent.endswith(("？", "！")) or any(
            w in sent for w in ["怒", "惊", "恨", "怕", "哭", "喊"]
        ):
            return clip_line(sent, 60), []

    warn = ["未定位到明显冲突句，已取首段作为核心冲突，建议人工复核"]
    return clip_line(sents[0], 60), warn


def build_hook(conflict: str, hook_type: str = "") -> Tuple[str, str]:
    """生成集末钩子（确定性规则：以核心冲突为素材，保证非空、非平淡陈述）。

    Returns: (钩子文本, 钩子类型)。hook_type 为空时自动从冲突内容推断。
    """
    if not conflict:
        conflict = "剧情骤然生变"
    if hook_type not in HOOK_TYPES:
        # 推断：冲突含反转/意外词 -> 反转；威胁词 -> 危机；疑问 -> 悬念；其余轮换新信息
        if any(k in conflict for k in ["却", "竟然", "居然", "没想到", "忽然", "突然", "发现", "真相", "秘密"]):
            hook_type = "反转"
        elif any(k in conflict for k in ["威胁", "杀", "逼", "夺", "抢", "危机", "危险"]):
            hook_type = "危机"
        elif conflict.endswith("？"):
            hook_type = "悬念"
        else:
            hook_type = "新信息"

    subject = conflict[:12].rstrip("，。！？")
    # 优先取第一小句（在逗号处截至断句），避免主语切在标点中间
    first_clause = re.split(r"[，、；：]", subject, maxsplit=1)[0].strip()
    if first_clause:
        subject = first_clause
    template_map = {
        "悬念": "就在此时，{subject}背后未解的谜团骤然浮出水面",
        "反转": "{subject}看似尘埃落定，真正的反转才刚刚开始",
        "危机": "危机悄然而至，{subject}已退无可退",
        "新信息": "一条关于{subject}的新线索突然出现，局面再生变数",
    }
    hook = template_map[hook_type].format(subject=subject)
    return hook, hook_type


def build_hook_en(conflict: str, hook_type: str = "") -> Tuple[str, str]:
    """英文模式生成集末钩子（确定性规则；hook_type 为空时自动推断）。"""
    if not conflict:
        conflict = "the plot suddenly changes"
    if hook_type not in HOOK_TYPES_EN:
        lower = conflict.lower()
        if any(k in lower for k in ["but", "turns out", "suddenly",
                                    "unexpectedly", "discover", "discovered",
                                    "truth", "secret", "reveal", "revealed"]):
            hook_type = "Twist"
        elif any(k in lower for k in ["threat", "danger", "kill", "kidnap",
                                      "force", "trap", "attack", "crisis",
                                      "hostage"]):
            hook_type = "Crisis"
        elif conflict.rstrip().endswith("?"):
            hook_type = "Suspense"
        else:
            hook_type = "New Info"

    subject = " ".join(conflict.split()[:12]).rstrip(".,!?")
    first_clause = re.split(r"[,;:]", " ".join(conflict.split()[:12]),
                            maxsplit=1)[0].strip()
    if first_clause:
        subject = first_clause
    # 过滤引导副词/连词（Suddenly/Then/But 等），避免钩子主语过短
    lead_words = {"suddenly", "then", "but", "however", "yet", "meanwhile",
                  "just", "so", "now", "after", "when", "before"}
    subj_words = subject.split()
    if subj_words and subj_words[0].strip(".,!?").lower() in lead_words:
        rest = " ".join(subj_words[1:])
        if rest:
            subject = rest
        else:            # 首段只有引导词（如 "Suddenly,"），取冲突句余下部分
            subject = " ".join(conflict.split()[1:12]).rstrip(".,!?").strip()
    template_map = {
        "Suspense": "Just then, the unresolved mystery behind {subject} resurfaces",
        "Twist": "{subject} seems settled, but the real twist has only just begun",
        "Crisis": "Crisis creeps in, and {subject} is left with no way back",
        "New Info": "A new clue about {subject} arrives out of nowhere, and everything shifts",
    }
    hook = template_map[hook_type].format(subject=subject)
    return hook, hook_type


def _plan_shots(
    text: str, target_duration: int, lines: List[Line],
    characters: List[Character], shots_per_minute: int = SHOTS_PER_MINUTE,
) -> List[Shot]:
    """生成分镜草稿：18--22 镜/分钟密度，单镜 2--5 秒，景别/运镜枚举。"""
    n = max(1, round(target_duration * shots_per_minute / 60))
    n = max(n, (target_duration + SHOT_MAX_DURATION - 1) // SHOT_MAX_DURATION)
    n = min(n, target_duration // SHOT_MIN_DURATION)
    base, rem = divmod(target_duration, n)
    durations = [base + (1 if i < rem else 0) for i in range(n)]

    lead = characters[0].name if characters else "主角"
    shot_size_seq = ["远景", "全景", "中景", "近景", "特写", "近景", "中景"]
    camera_seq = ["固定", "推", "拉", "摇", "移", "跟随"]

    shots: List[Shot] = []
    for i in range(n):
        if i == 0:
            size = "远景"
        elif i == n - 1:
            size = "特写"
        else:
            size = shot_size_seq[i % len(shot_size_seq)]
        camera = camera_seq[i % len(camera_seq)]
        # 台词按镜头序号均布到整集；无台词镜头保留空缺，避免每镜都讲话
        if lines:
            line_idx = min(len(lines) - 1, round(i * len(lines) / n))
            line = lines[line_idx]
            dialogue = line.text
            speaker = line.speaker
        else:
            dialogue, speaker = None, lead
        emotion = "专注"
        expression, tone = EMOTION_DICT[emotion]
        visual = clip_line(
            f"{speaker}在场景内推进剧情，动作与位置配合本镜情绪变化", 48
        )
        shots.append(
            Shot(
                shot=i + 1,
                shot_size=size,
                camera=camera,
                visual=visual,
                dialogue=dialogue,
                character=speaker,
                emotion=emotion,
                expression=expression,
                tone=tone,
                duration=durations[i],
            )
        )
    return shots


def _plan_shots_en(
    text: str, target_duration: int, lines: List[Line],
    characters: List[Character], shots_per_minute: int = SHOTS_PER_MINUTE,
) -> List[Shot]:
    """英文模式生成分镜草稿：18--22 镜/分钟密度，单镜 2--5 秒。"""
    n = max(1, round(target_duration * shots_per_minute / 60))
    n = max(n, (target_duration + SHOT_MAX_DURATION - 1) // SHOT_MAX_DURATION)
    n = min(n, target_duration // SHOT_MIN_DURATION)
    base, rem = divmod(target_duration, n)
    durations = [base + (1 if i < rem else 0) for i in range(n)]

    lead = characters[0].name if characters else "Protagonist"
    shot_size_seq = ["Wide", "Full", "Medium", "Close-up", "Close-up", "Medium"]
    camera_seq = ["Static", "Push in", "Pull back", "Pan", "Tilt", "Track"]

    shots: List[Shot] = []
    for i in range(n):
        if i == 0:
            size = "Wide"
        elif i == n - 1:
            size = "Close-up"
        else:
            size = shot_size_seq[i % len(shot_size_seq)]
        camera = camera_seq[i % len(camera_seq)]
        if lines:
            line_idx = min(len(lines) - 1, round(i * len(lines) / n))
            line = lines[line_idx]
            dialogue = line.text
            speaker = line.speaker
        else:
            dialogue, speaker = None, lead
        emotion = "Focused"
        expression, tone = EMOTION_DICT_EN[emotion]
        visual = clip_by_words(
            f"{speaker} advances the plot in the scene, moves and positions "
            f"fitting this shot's mood", 25
        )
        shots.append(
            Shot(
                shot=i + 1,
                shot_size=size,
                camera=camera,
                visual=visual,
                dialogue=dialogue,
                character=speaker,
                emotion=emotion,
                expression=expression,
                tone=tone,
                duration=durations[i],
            )
        )
    return shots


def _build_episode_en(
    chunk: str, episode_no: int, target_duration: int,
    prev_hook: str = "", shots_per_minute: int = SHOTS_PER_MINUTE,
) -> Episode:
    """由一个文本块构建一集（英文模式）。"""
    warnings: List[str] = []
    conflict, conflict_warn = _extract_core_conflict_en(chunk)
    warnings.extend(conflict_warn)
    if len(conflict.split()) < CONFLICT_MIN_LENGTH:
        conflict = "The plot advances into the unknown as the conflict escalates"
        warnings.append("Core conflict is too short; fallback text used")

    hook, hook_type = build_hook_en(conflict)
    if len(hook.split()) < HOOK_MIN_LENGTH:
        hook, hook_type = "The situation changes abruptly, and crisis is imminent", "Crisis"

    scenes = _extract_scenes_en(chunk)
    characters = _extract_characters_en(chunk)
    lines = _extract_lines_en(chunk, [c.name for c in characters])
    if not lines:
        warnings.append("No dialogue extracted; consider adding conversation or narration")

    continuity = f"Continuing from episode {episode_no - 1}: {prev_hook}" if prev_hook else ""
    shots = _plan_shots_en(chunk, target_duration, lines, characters,
                           shots_per_minute)

    return Episode(
        episode=episode_no,
        target_duration=target_duration,
        core_conflict=conflict,
        episode_hook=hook,
        hook_type=hook_type,
        scenes=scenes,
        characters=characters,
        lines=lines,
        shots=shots,
        continuity=continuity,
        warnings=warnings,
        source_text=chunk,
        language="en",
    )


def _build_episode(
    chunk: str, episode_no: int, target_duration: int,
    prev_hook: str = "", shots_per_minute: int = SHOTS_PER_MINUTE,
    language: str = "zh",
) -> Episode:
    """由一个文本块构建一集（language: zh/en）。"""
    if language == "en":
        return _build_episode_en(chunk, episode_no, target_duration,
                                 prev_hook, shots_per_minute)
    warnings: List[str] = []
    conflict, conflict_warn = _extract_core_conflict(chunk)
    warnings.extend(conflict_warn)
    if len(conflict) < CONFLICT_MIN_LENGTH:
        conflict = "剧情在未知中推进，冲突升级"
        warnings.append("核心冲突过短，已用兜底文案")

    hook, hook_type = build_hook(conflict)
    if len(hook) < HOOK_MIN_LENGTH:
        hook, hook_type = "局面骤然生变，危机一触即发", "危机"

    scenes = _extract_scenes(chunk)
    characters = _extract_characters(chunk)
    lines = _extract_lines(chunk, [c.name for c in characters])
    if not lines:
        warnings.append("未提取到台词，建议补充对话或旁白")

    continuity = f"承接第 {episode_no - 1} 集：{prev_hook}" if prev_hook else ""
    shots = _plan_shots(chunk, target_duration, lines, characters,
                        shots_per_minute)

    return Episode(
        episode=episode_no,
        target_duration=target_duration,
        core_conflict=conflict,
        episode_hook=hook,
        hook_type=hook_type,
        scenes=scenes,
        characters=characters,
        lines=lines,
        shots=shots,
        continuity=continuity,
        warnings=warnings,
        source_text=chunk,
    )


# ------------------- 主入口 -------------------


# 章节标题模式（卷/章/回/篇/部，支持中文数字与阿拉伯数字）
_CHAPTER_TITLE_RE = re.compile(
    r"^第[0-9一二三四五六七八九十百千〇零]{1,6}[卷篇章回部](?:[\s:：、\-—]|$)"
)

# 英文章节标题模式（Chapter/Part/Act/Episode/Scene/Volume/Book + 数字或罗马数字）
_CHAPTER_TITLE_RE_EN = re.compile(
    r"^(?:chapter|part|act|episode|scene|volume|book)\s+"
    r"[0-9]{1,4}|[ivxlcdm]{1,8}(?:[\s:：.\-—]|$)",
    re.IGNORECASE,
)


def _is_pure_title_block(text: str) -> bool:
    """判断文本块是否只是章节标题（无正文字句，不应独立成集）。

    例如大纲开头的「第一卷 初入江湖」或 "Chapter 1"。
    含正文（句末标点）或过长的块不算。
    """
    s = text.strip()
    if not s or len(s) > 30:
        return False
    if any(p in s for p in "。！？；"):
        return False
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return bool(lines) and all(
        _CHAPTER_TITLE_RE.match(ln) or _CHAPTER_TITLE_RE_EN.match(ln)
        for ln in lines
    )


def _merge_pure_title_blocks(chunks: List[str]) -> List[str]:
    """把纯章节标题块并入下一个有正文的块，避免卷/章标题单独成集。"""
    merged: List[str] = []
    pending = ""
    for chunk in chunks:
        c = chunk.strip()
        if not c:
            continue
        if _is_pure_title_block(c):
            pending = c
            continue
        if pending:
            c = pending + "\n" + c
            pending = ""
        merged.append(c)
    if pending:
        merged.append(pending)   # 兜底：全文只有标题时保留
    return merged


def split_episodes(
    parse_result: ip.ParseResult,
    target_duration: int = DEFAULT_TARGET_DURATION,
    shots_per_minute: int = SHOTS_PER_MINUTE,
) -> EpisodePlan:
    """由 T06 ParseResult 拆分集剧本（强钩子拆集）。

    分段策略（引用 M0-5 T05）：大纲按章节保留语义拆集；小说片段/梗概按块拆集，
    输出后自动重编号集序并生成集间衔接。
    """
    shots_per_minute = max(18, min(22, shots_per_minute))
    target_duration = max(60, min(90, target_duration))

    chunk_texts = list(parse_result.chunks or [])
    if not chunk_texts and parse_result.cleaned_text:
        chunk_texts = [parse_result.cleaned_text]
    if not chunk_texts:
        raise ValueError("输入为空，无法拆集")
    chunk_texts = _merge_pure_title_blocks(chunk_texts)

    episodes: List[Episode] = []
    warnings: List[str] = []
    prev_hook = ""
    language = getattr(parse_result, "language", "zh")
    for i, chunk in enumerate(chunk_texts, start=1):
        if not chunk.strip():
            continue
        ep = _build_episode(chunk, i, target_duration, prev_hook,
                            shots_per_minute, language=language)
        episodes.append(ep)
        prev_hook = ep.episode_hook
        warnings.extend(ep.warnings)

    if parse_result.input_type == ip.TYPE_ONE_LINE and parse_result.needs_expansion:
        if language == "en":
            warnings.insert(
                0, "Input is a one-line idea; consider expanding it into a "
                   "full draft script before splitting"
            )
        else:
            warnings.insert(
                0, "输入为一句话创意，建议先按 V1 模板扩写为剧本底稿后再拆集"
            )

    return EpisodePlan(
        episodes=episodes,
        input_type=parse_result.input_type,
        input_type_label=parse_result.input_type_label,
        needs_expansion=parse_result.needs_expansion,
        sensitive_hits=list(parse_result.sensitive_hits),
        warnings=warnings,
        language=language,
    )


def split_episodes_from_text(
    raw_text: str,
    template: Optional[str] = None,
    target_duration: int = DEFAULT_TARGET_DURATION,
    shots_per_minute: int = SHOTS_PER_MINUTE,
) -> EpisodePlan:
    """完整链路：T06 解析 -> T07 拆集。"""
    parse_result = ip.parse_input(raw_text, template=template)
    return split_episodes(parse_result, target_duration, shots_per_minute)


# ------------------- 校验 -------------------


def validate_plan(plan: EpisodePlan) -> List[str]:
    """逐项校验 T01/T02 约束，返回违规列表（空列表 = 通过）。

    覆盖：集序、时长、核心冲突/钩子长度与类型、场景字段、角色枚举、
    台词单句字数/词数、分镜景别/运镜/时长/密度。校验失败项用于测试与 T21 质量自检。
    英文模式（plan.language == "en"）按英文枚举与词数校验。
    """
    problems: List[str] = []
    eps = plan.episodes
    if not eps:
        return ["拆集结果为空"]

    en = getattr(plan, "language", "zh") == "en"
    hook_types = HOOK_TYPES_EN if en else HOOK_TYPES
    times = SCENE_TIMES_EN if en else SCENE_TIMES
    roles = CHARACTER_ROLES_EN if en else CHARACTER_ROLES
    sizes = SHOT_SIZES_EN if en else SHOT_SIZES
    cams = CAMERAS_EN if en else CAMERAS
    emotions = EMOTION_DICT_EN if en else EMOTION_DICT

    for idx, ep in enumerate(eps, start=1):
        if en:
            tag = f"Episode {ep.episode}"
        else:
            tag = f"第{ep.episode}集"
        if ep.episode != idx:
            problems.append(f"{tag}：集序应为 {idx}，实际 {ep.episode}")
        if not 60 <= ep.target_duration <= 90:
            problems.append(f"{tag}：目标时长 {ep.target_duration} 超出 60--90 秒")
        if en:
            if len(ep.core_conflict.split()) < CONFLICT_MIN_LENGTH:
                problems.append(f"{tag}：核心冲突过短 ({len(ep.core_conflict.split())} 词)")
            if len(ep.episode_hook.split()) < HOOK_MIN_LENGTH:
                problems.append(f"{tag}：集末钩子过短 ({len(ep.episode_hook.split())} 词)")
        else:
            if len(ep.core_conflict) < CONFLICT_MIN_LENGTH:
                problems.append(f"{tag}：核心冲突过短 ({len(ep.core_conflict)} 字)")
            if len(ep.episode_hook) < HOOK_MIN_LENGTH:
                problems.append(f"{tag}：集末钩子过短 ({len(ep.episode_hook)} 字)")
        if ep.hook_type not in hook_types:
            problems.append(f"{tag}：钩子类型 {ep.hook_type} 不在枚举内")
        if not ep.scenes:
            problems.append(f"{tag}：场景序列为空")
        for sc in ep.scenes:
            if sc.time not in times:
                problems.append(f"{tag}：场景时间 {sc.time} 不在枚举内")
        for ch in ep.characters:
            if ch.role not in roles:
                problems.append(f"{tag}：角色类型 {ch.role} 不在枚举内")
        for ln in ep.lines:
            if en:
                if len(ln.text.split()) > LINE_MAX_WORDS:
                    problems.append(f"{tag}：台词超 {LINE_MAX_WORDS} 词：{ln.text}")
            else:
                if len(ln.text) > LINE_MAX_LENGTH:
                    problems.append(f"{tag}：台词超 {LINE_MAX_LENGTH} 字：{ln.text}")
        if not ep.shots:
            problems.append(f"{tag}：分镜草稿为空")
            continue
        total = sum(s.duration for s in ep.shots)
        if total != ep.target_duration:
            problems.append(f"{tag}：分镜总时长 {total} != 目标时长 {ep.target_duration}")
        for s in ep.shots:
            if s.shot_size not in sizes:
                problems.append(f"{tag}：景别 {s.shot_size} 不在枚举内")
            if s.camera not in cams:
                problems.append(f"{tag}：运镜 {s.camera} 不在枚举内")
            if not SHOT_MIN_DURATION <= s.duration <= SHOT_MAX_DURATION:
                problems.append(f"{tag}：镜时长 {s.duration} 超出 2--5 秒")
            if s.emotion not in emotions:
                problems.append(f"{tag}：情绪 {s.emotion} 不在词典内")
        actual_per_min = len(ep.shots) / ep.target_duration * 60
        if not 18 <= actual_per_min <= 22:
            problems.append(
                f"{tag}：分镜密度 {actual_per_min:.1f} 镜/分钟超出 18--22"
            )
    return problems


# ------------------- 渲染 -------------------


def _line_to_md(ln: Line, language: str = "zh") -> str:
    if language == "en":
        who = "Narrator" if ln.speaker == "Narrator" else ln.speaker
        return f"- [{who}] (tone: {ln.tone}) \"{ln.text}\""
    who = "旁白" if ln.speaker == "旁白" else ln.speaker
    return f"- 【{who}】（语气：{ln.tone}）“{ln.text}”"


def render_markdown(plan: EpisodePlan, with_shots: bool = True) -> str:
    """按 M0-1 Markdown 模板渲染全部分集剧本（含可选分镜表）。

    英文模式（plan.language == "en"）使用英文框架标签。
    """
    en = getattr(plan, "language", "zh") == "en"
    out: List[str] = []
    if en:
        out.append(f"# Episode Scripts (input type: {plan.input_type_label})")
        if plan.needs_expansion:
            out.append("> Tip: the input is a one-line idea; consider "
                       "expanding it into a draft script first.")
    else:
        out.append(f"# 分集剧本（输入类型：{plan.input_type_label}）")
        if plan.needs_expansion:
            out.append("> 提示：输入为一句话创意，建议先扩写为剧本底稿。")
    if plan.sensitive_hits:
        if en:
            out.append("> ⚠ Sensitive categories hit: "
                       f"{'、'.join(plan.sensitive_hits)} "
                       "(please review before continuing)")
        else:
            out.append(f"> ⚠ 命中红线类别：{'、'.join(plan.sensitive_hits)}（请人工确认后继续）")

    for ep in plan.episodes:
        out.append("")
        if en:
            out.append(f"## Episode {ep.episode} (target 60--90 seconds)")
            if ep.continuity:
                out.append(f"- Continuing: {ep.continuity}")
            out.append(f"- Core conflict: {ep.core_conflict}")
            out.append(f"- Episode hook ({ep.hook_type}): {ep.episode_hook}")
            out.append("")
            out.append("### Characters")
            for ch in ep.characters:
                out.append(f"- {ch.name} ({ch.description})")
            if ep.relations:
                out.append("")
                out.append("### Character relations")
                for rel in ep.relations:
                    out.append(
                        f"- {rel.get('source')} x {rel.get('target')}"
                        f" ({rel.get('rel_type')}): {rel.get('evidence')}"
                    )
            out.append("")
            out.append("### Scenes")
            for sc in ep.scenes:
                out.append(
                    f"{sc.id}. Scene: {sc.location} ({sc.time}, "
                    f"interior/exterior) -- {sc.setting}"
                )
            out.append("")
            out.append("### Dialogue & narration")
            for ln in ep.lines:
                out.append(_line_to_md(ln, "en"))
            if with_shots and ep.shots:
                out.append("")
                out.append("### Shot drafts (for module 2)")
                out.append("| Shot | Size | Camera | Visual | Dialogue/Narration "
                           "| Character | Emotion | Expression | Tone | Duration |")
                out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
                for s in ep.shots:
                    dialogue = s.dialogue if s.dialogue else "(none)"
                    out.append(
                        f"| {s.shot} | {s.shot_size} | {s.camera} | {s.visual} "
                        f"| {dialogue} | {s.character} | {s.emotion} | "
                        f"{s.expression} | {s.tone} | {s.duration} |"
                    )
        else:
            out.append(f"## 第 {ep.episode} 集（目标时长 60--90 秒）")
            if ep.continuity:
                out.append(f"- 承接：{ep.continuity}")
            out.append(f"- 核心冲突：{ep.core_conflict}")
            out.append(f"- 集末钩子（{ep.hook_type}）：{ep.episode_hook}")
            out.append("")
            out.append("### 出场角色")
            for ch in ep.characters:
                out.append(f"- {ch.name}（{ch.description}）")
            if ep.relations:
                out.append("")
                out.append("### 角色关系")
                for rel in ep.relations:
                    out.append(
                        f"- {rel.get('source')} × {rel.get('target')}"
                        f"（{rel.get('rel_type')}）：{rel.get('evidence')}"
                    )
            out.append("")
            out.append("### 场景序列")
            for sc in ep.scenes:
                out.append(f"{sc.id}. 场景：{sc.location}（{sc.time}，内/外）——{sc.setting}")
            out.append("")
            out.append("### 对白与旁白")
            for ln in ep.lines:
                out.append(_line_to_md(ln))
        if with_shots and ep.shots and not en:
            out.append("")
            out.append("### 分镜草稿（供模块二细化）")
            out.append("| 镜号 | 景别 | 运镜 | 画面内容 | 台词/旁白 | 角色 | 情绪 | 表情 | 音调 | 时长 |")
            out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            for s in ep.shots:
                dialogue = s.dialogue if s.dialogue else "（无）"
                out.append(
                    f"| {s.shot} | {s.shot_size} | {s.camera} | {s.visual} | {dialogue} "
                    f"| {s.character} | {s.emotion} | {s.expression} | {s.tone} | {s.duration} |"
                )
        if ep.warnings:
            out.append("")
            if en:
                out.append(f"> Generation notes: {'; '.join(ep.warnings)}")
            else:
                out.append(f"> 生成提示：{'；'.join(ep.warnings)}")
    return "\n".join(out)


def render_json(plan: EpisodePlan) -> str:
    """输出 JSON（episodes 数组，字段对齐 T01/T02 Schema）。"""
    return json.dumps(asdict(plan), ensure_ascii=False, indent=2)