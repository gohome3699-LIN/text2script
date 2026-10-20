# -*- coding: utf-8 -*-
"""T08 角色与关系线提取：深化 T07 角色识别。

对应《纯文转剧本单点工具开发清单》T08 与 M0 规则定稿 T03（V1 强钩子拆集模板
第 3 条「拆出主角/配角/反派的关系线」）。在 T07 基础角色提取之上，本模块：

1. 补齐说话动词与名字隔词/隔动作时名字漏提的场景（如「李强推开门，急切说道」、
   「林风握紧剑柄，沉声道」），并把新发现的说话人补入角色清单；
2. 对纯叙述文段做角色推断：无对话素材（如故事梗概）中按「称谓/亲属前缀 +
   关联词 + 句首主语」挖掘候选角色，避免角色降级为占位「主角」；
3. 提取对抗/同盟/亲情/主从/爱慕/交易六类关系线，生成人物关系摘要；
   输出对齐 M0-1 角色字段，Episode.relations 可随 JSON/反渲染序列化；
4. 消费 T06 ParseResult / T07 EpisodePlan 接口，预留 T09（钩子生成）与
   T10（剧本导出）衔接点。

仅使用 Python 标准库，适配无 GUI 的 Linux 沙箱（Python 3.12）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from itertools import combinations
from typing import Dict, List, Optional

import input_parser as ip
import episode_splitter as es


# ------------------- 角色关系类型（对齐 T03「主角/配角/反派关系线」） -------------------

RELATION_TYPES = ["对抗", "同盟", "亲情", "主从", "爱慕", "交易"]


@dataclass
class CharacterRelation:
    """一条角色关系线：两端角色 + 关系类型 + 证据原文。"""

    source: str
    target: str
    rel_type: str
    evidence: str


# 关系线索词（叙述句中命中即触发；要求句内至少出现两个已知角色名）
_RELATION_RULES: Dict[str, tuple] = {
    "对抗": (
        "仇", "怨", "杀", "敌", "背叛", "反目", "逼", "夺", "抢", "威胁",
        "冲突", "抓", "战", "恨", "怒", "打", "斗", "追杀", "围攻", "镇压",
        "血洗", "死对头",
    ),
    "同盟": (
        "帮", "救", "联手", "合作", "同伴", "并肩", "一起", "相助",
        "支援", "结盟", "战友", "同伙", "相救",
    ),
    "亲情": (
        "父亲", "母亲", "爹", "娘", "哥哥", "弟弟", "姐姐", "妹妹", "兄妹",
        "姐弟", "父子", "父女", "母子", "母女", "家人", "妻子", "丈夫",
        "夫妻", "儿子", "女儿", "师父", "弟子", "徒弟", "娶", "嫁", "成亲",
    ),
    "主从": (
        "效忠", "主人", "属下", "手下", "仆人", "跟随", "少主", "主公",
        "臣服", "家丁", "护卫", "侍从",
    ),
    "爱慕": (
        "喜欢", "爱", "心动", "暗恋", "心仪", "倾心", "爱慕", "痴迷",
    ),
    "交易": (
        "交易", "买卖", "雇佣", "契约", "报酬", "代价", "佣金", "委托",
    ),
}

# 亲情称谓（单角色 + 称谓词的句子，关系对象未命名时用称谓占位）
_KINSHIP_TERMS = (
    "父亲", "母亲", "爹", "娘", "哥哥", "弟弟", "姐姐", "妹妹", "丈夫",
    "妻子", "儿子", "女儿", "师父", "弟子", "徒弟", "爷爷", "奶奶",
    "外公", "外婆",
)

# 联合短语（「X与Y联手/并肩/合作」等，用于设定明确的同盟对象，
# 避免同句里「联手迎战 Z」把 Z 也误配成同盟）
_ALLY_RE = re.compile(
    r"([\u4e00-\u9fa5]{2,3})[与和]([\u4e00-\u9fa5]{2,3})"
    r"(?:联手|合作|一起|并肩|结盟|相救|相助)"
)

# 后置联合结构（「归来，与苏婉联手」）：左主语被逗号/其他成分隔开，
# 只取联合动词前的角色名，用于纯叙述角色挖掘（不参与关系配对）
_ALLY_HUNT_RE = re.compile(
    r"[与和]([\u4e00-\u9fa5]{2,3})"
    r"(?:联手|合作|一起|并肩|结盟|相救|相助|同行|同往)"
)


# ------------------- 增强说话人识别 -------------------


# 扩展说话动词表（T07 基表 + 常见口语/书面动词；顺序长词优先）
_EXTRA_SPEECH_VERBS = (
    "怒喝", "厉喝", "喝斥", "呵斥", "斥道", "追问", "叹道", "劝道",
    "笑问", "反问", "命令", "吩咐", "安抚", "惊呼", "嘀咕", "嘟囔",
    "咆哮", "骂道",
)
_EXTENDED_SPEECH_VERBS = es._SPEECH_VERBS + _EXTRA_SPEECH_VERBS
_EXT_VERB_PATTERN = "|".join(_EXTENDED_SPEECH_VERBS)
_EXT_VERB_RE = re.compile("(?:" + _EXT_VERB_PATTERN + ")$")

# 对宾动词：后面通常跟动作对象（「盯着林风」），该对象不应被当作说话人
_OBJECT_VERBS = (
    "盯着", "看着", "瞪着", "望着", "拦住", "拉住", "拽住", "抓着",
    "拉着", "推到", "推向", "甩开", "按住", "抱着", "冲向", "对着",
    "朝着",
)

# 谓词动作动词：说话短语中「主语 + 动作 + 说话动词」结构的动作部分，
# 用于在不依赖已知角色名时直接挖掘说话人主语
_ACTION_VERBS = (
    "推开", "推门", "放下", "抽出", "拔出", "握紧", "握起", "站起",
    "站起来", "起身", "转身", "回头", "皱眉", "叹了口气", "拍案",
    "抬头", "低头", "瞪了", "看了", "望了", "压低",
)

# 身份/泛称黑名单（2~3 字非人名词，纯叙述挖掘与说话人过滤共用）
_NAME_BLACKLIST = (
    "商人", "老者", "少年", "少女", "男子", "女子", "姑娘", "女人",
    "男人", "高手", "众人", "两人", "三人", "几人", "大家", "双方",
    "老板", "夫人", "小姐", "少爷", "和尚", "道士", "神仙", "妖怪",
    "路人", "村民", "士兵", "将军", "王爷", "皇帝", "皇后", "太子",
    "公主", "大爷", "大娘", "小孩", "孩子", "仆人", "属下", "侍卫",
    "护卫", "掌柜", "小二", "弟子", "徒弟", "师父", "师兄", "师妹",
    "师弟", "师姐", "兄弟", "朋友", "敌人", "仇家", "杀手", "镖师",
    "书生", "官员", "臣子", "声音", "心中", "身上", "眼前", "身后",
)

# 代词子串（名字候选含其中任一即拒绝，防止「他」「她一」等被当角色名）
_PRONOUN_SUBSTRINGS = ("他", "她", "它")

# 称谓/亲属前缀 + 2~3 字名（纯叙述挖掘模式）。
# 含格标记「被/与」：常见被动与联合句式（「被赵屠夫一掌」/「与苏婉联手」）。
_NAME_PREFIXES = (
    "少年", "少女", "青年", "老者", "老妇", "男子", "女子", "男孩",
    "女孩", "中年", "年轻", "落魄", "神秘", "红衣", "黑衣", "白衣",
    "之女", "之妻", "之子", "之兄", "之妹", "名叫", "唤作", "仇家",
    "被", "与",
)

_PROXY_NAMES = ("主角", "配角")

# 人名后常见动词/虚词尾巴（整词匹配，用于从「前缀+名+动词」中还原名字
# 如「少年王尘修为尽废」→ 王尘；「之女苏婉成亲当日」→ 苏婉）
_NAME_TAIL_VERBS = (
    "来到", "走进", "回到", "走出", "出现在", "站在", "坐在", "看向",
    "望向", "盯着", "看着", "听着", "想着", "说着", "开口道", "冷笑道",
    "沉声道", "厉声道", "大喝一声", "缓缓", "慢慢", "突然", "忽然",
    "竟然", "却是", "知道", "明白", "发现", "修为", "拔出", "抽出",
    "拔出剑", "拔剑", "出手", "挥剑", "提剑", "握紧", "提起", "转身",
    "回头", "离开", "走向", "成亲", "回来了", "回来", "开口", "拱手",
    "抱拳", "跪在", "跪倒", "抬起头", "低下头", "上前", "站起", "起身",
    "一言不发", "脱险", "脱身", "救出", "逃出",
)

# 名字前的单字动作动词（「老者收林风为徒」→ 前提「收」后才是名；
# 用于从前缀贪婪吞入的「动词+名+…」中还原真实名字）
_LEADING_ACTION_VERBS = frozenset(
    "收救带领携扶抱背拉推拦挡护追押杀打抢夺放叫唤",
)

# 名字后粘合尾巴（整词或首字）：虚词/格标记/状态副词/动量词，
# 用于「名+（虚词/副词+动词）」结构还原名字，如「林风为救」「赵屠夫一掌」
_NAME_TAIL_GLUE = (
    "为", "被", "将", "把", "与", "和", "向", "对", "在", "从",
    "之", "的", "地", "一掌", "一拳", "一脚", "一刀", "一把",
    "狠狠", "猛地", "轻轻", "微微", "淡淡", "冷冷", "终于", "竟",
)
_NAME_TAIL_GLUE_FIRST = frozenset("为被将与和向对在从之地的一")


def _candidate_ok(name: str) -> bool:
    """候选角色名合法性：2~3 字、不在身份黑名单、不含代词、像人名。"""
    if not name or len(name) < 2 or len(name) > 3:
        return False
    if name in _NAME_BLACKLIST:
        return False
    if any(p in name for p in _PRONOUN_SUBSTRINGS):
        return False
    return es._looks_like_name(name)


def _speaker_from_phrase(phrase: str, known_names: List[str]) -> Optional[str]:
    """从「X动作，说话动词」/「X说话动词」短语中定位已知角色说话人。

    规则：剥离说话动词后，取短语中按原文顺序最靠前的已知角色名为主语；
    若该名字紧跟在「盯着/看着…」等对宾动词后且前方无其他已知角色，
    说明它是动作对象而非说话人，保守不归属；黑名单身份词不归属。
    """
    p = phrase.strip().rstrip("，, ")
    stripped = _EXT_VERB_RE.sub("", p).strip().rstrip("，, ")
    if not stripped:
        return None
    hits = [
        (n, stripped.find(n))
        for n in known_names
        if n and n in stripped and n not in _NAME_BLACKLIST
    ]
    if not hits:
        return None
    hits.sort(key=lambda kv: kv[1])
    name, idx = hits[0]
    pre = stripped[:idx]
    if len(hits) == 1 and any(pre.endswith(ov) for ov in _OBJECT_VERBS):
        return None
    return name


def _discover_speaker_from_phrase(stripped: str) -> Optional[str]:
    """在说话动词短语中直接挖掘说话人（不依赖已知角色名）。

    方法：定位首个谓词动作动词，取动词前 2~3 字为主语候选并做黑名单/人名过滤。
    无谓词动作时保守不推断（避免把「敌方首领盯着林风」的宾语当说话人）。
    """
    if not stripped:
        return None
    for verb in _ACTION_VERBS:
        idx = stripped.find(verb)
        if idx <= 0:
            continue
        subject = stripped[:idx].strip("，, ")
        if not subject:
            continue
        cand = subject[-3:] if len(subject) > 3 else subject
        if not _candidate_ok(cand):
            continue
        return cand
    return None


def _speaker_for_phrase(phrase: str, known_names: List[str]) -> Optional[str]:
    """综合定位说话人：优先已知角色名匹配，其次从短语结构直接挖掘。"""
    sp = _speaker_from_phrase(phrase, known_names)
    if sp:
        return sp
    stripped = _EXT_VERB_RE.sub("", phrase.strip()).strip().rstrip("，, ")
    return _discover_speaker_from_phrase(stripped)


# 增强说话人正则：以句首/句号/换行为锚点，X（动作/表情，2~28 字）说话动词：台词
_REL_SPEAKER_RE = re.compile(
    r"(?:^|[。！？；\n])([\u4e00-\u9fa5A-Za-z0-9，、·\s]{2,28}?"
    r"(?:" + _EXT_VERB_PATTERN + r"))"
    r"[：:][“\"]([^“”\"\n]{1,120})[”\"]",
    re.MULTILINE,
)


def assign_line_speakers(
    text: str, lines: List[es.Line], known_names: List[str],
) -> List[es.Line]:
    """增强台词归属：把 T07 中无法归属而落到旁白的
    「X动作，说话动词：台词」结构的行归属到说话人；其余保持原样。
    返回新列表，不改动原列表。
    """
    new_lines = [
        es.Line(speaker=ln.speaker, tone=ln.tone, text=ln.text)
        for ln in lines
    ]
    for m in _REL_SPEAKER_RE.finditer(text):
        speaker = _speaker_for_phrase(m.group(1), known_names)
        if not speaker:
            continue
        clipped = es.clip_line(m.group(2))
        if not clipped:
            continue
        for ln in new_lines:
            if ln.speaker == "旁白" and ln.text == clipped:
                ln.speaker = speaker
                break
    return new_lines


# ------------------- 纯叙述角色挖掘 -------------------


# 句首主语模式：行首 2~3 字名 + 后接介词/虚词/常用行为动词首字/标点
# （如「林风为救店家女…」「林风醒来后…」「苏婉不离不弃」）
_SENT_HEAD_NAME_RE = re.compile(
    r"^([\u4e00-\u9fa5]{2,3})"
    r"(?=[为和与同随被对向不，。！？；：是]|醒|笑|哭|怒|拔|握|站|坐|"
    r"回|来|走|点|摇|叹|皱|低|抬|望|看|想|说|问|沉|淡|冷|轻|微|转|跟|跪|冲|追)",
    re.MULTILINE,
)


def _strip_name_tail(raw: str) -> str:
    """尝试把候选串还原为「2~3 字名」（名后剩余必须为空、整词尾巴或粘合字开头）。

    先从 3 字候选开始，剩余非动词尾巴/粘合字则回退 2 字，避免吞入后续词
    （如「林风来到」取「林风」而非「林风来」；「林风为救」取「林风」）。
    整词动词尾巴优先于粘合字：若存在更短候选使剩余串以整词尾巴开头
    （「王尘修为尽废」→ n=2 时「修为」是整词尾巴），则跳过当前 3 字候选，
    防止把「王尘修+为尽废」误当作名字+粘合字。
    若候选以单字动作动词开头（「收林风为徒」的「收」），去掉动词后重新剥离，
    剥离失败时宁可不提，避免把「动词+名」误当角色名。
    """
    for n in (3, 2):
        cand = raw[:n]
        if not _candidate_ok(cand):
            continue
        rest = raw[n:]
        if not rest:
            if cand[0] in _LEADING_ACTION_VERBS:
                return _strip_name_tail(raw[1:])
            return cand
        if any(rest.startswith(v) for v in _NAME_TAIL_VERBS):
            if cand[0] in _LEADING_ACTION_VERBS:
                return _strip_name_tail(raw[1:])
            return cand
        # 存在更短候选使剩余串以整词尾巴开头 → 交给更短候选
        if any(raw[m:].startswith(v)
               for m in range(n - 1, 1, -1)
               for v in _NAME_TAIL_VERBS):
            continue
        if (any(rest.startswith(v) for v in _NAME_TAIL_GLUE)
                or rest[0] in _NAME_TAIL_GLUE_FIRST):
            if cand[0] in _LEADING_ACTION_VERBS:
                return _strip_name_tail(raw[1:])
            return cand
    return ""


def discover_narration_names(text: str, max_names: int = 5) -> List[str]:
    """纯叙述文本中挖掘候选角色名。

    四种模式：称谓/亲属/格标记前缀 + 2~3 字名（后接动词/粘合字时剥离尾巴，
    如「少年王尘修为尽废」→ 王尘、「林风为救」→ 林风、「被赵屠夫一掌」→ 赵屠夫）；
    「X与Y」关联结构；「与Z联手」后置联合结构；行首主语 + 介词/行为动词。
    只用于 T07 只给出占位角色（无任何明确说话人）的场景，避免噪音覆盖。
    返回按出现频次降序去重后的名字列表。
    """
    freq: Dict[str, int] = {}
    base = text.replace("\n", "。")

    def _count(cand: str) -> None:
        if _candidate_ok(cand):
            freq[cand] = freq.get(cand, 0) + 1

    for prefix in _NAME_PREFIXES:
        # 名字后可能紧跟动词/虚词（修为/为救/一掌…），贪婪多取 2~5 字再剥离尾巴
        pat = re.compile(
            re.escape(prefix) + r"([\u4e00-\u9fa5]{2,5})"
        )
        for m in pat.finditer(base):
            _count(_strip_name_tail(m.group(1)))

    for m in _ALLY_RE.finditer(base):
        _count(m.group(1))
        _count(m.group(2))

    # 后置联合结构（「十年后归来，与苏婉联手迎战」）：左主语被其他成分隔开
    for m in _ALLY_HUNT_RE.finditer(base):
        _count(m.group(1))

    for m in _SENT_HEAD_NAME_RE.finditer(text):
        _count(m.group(1))

    ordered = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [n for n, _ in ordered[:max_names]]


def infer_narration_actors(text: str, known_names: List[str]) -> Dict[str, int]:
    """纯叙述角色推断：从剔除了对话的叙述句中，识别句子开头 12 字内的动作主体。

    返回 {角色名: 作为句首主体出现次数}。用于判断哪个角色是场景主控。
    """
    narration = re.sub(r"[“\"][^“”\"\n]{1,120}[”\"]", "", text)
    counts: Dict[str, int] = {}
    for sent in es._split_sentences(narration):
        head = sent[:12]
        for n in known_names:
            if n and n in head:
                counts[n] = counts.get(n, 0) + 1
                break
    return counts


# ------------------- 关系线提取 -------------------

# 逗号/顿号片段切分（用于限定对抗/同盟配对范围，减少复合句噪音）
_SEG_SPLIT_RE = re.compile(r"[，,、；;]")

# 动作型对抗词（有具体施/受动作）；静态情绪/关系词（仇/恨/怒/怨/敌/背叛等）
# 语义上不指向明确对象，不做跨片段配对，避免「A发誓报仇」误配「B对抗」
_ACTION_CONFLICT_TERMS = (
    "战", "打", "斗", "杀", "追杀", "围攻", "镇压", "血洗", "抓", "夺",
    "抢", "逼", "刺", "砍", "斩", "击", "攻", "挟持", "下毒", "灭门",
)


def _union_pairs(sent: str, names: List[str]) -> set:
    """识别明确联合对（「X与Y联手」；「归来，与苏婉联手」左名被隔开时回溯）。

    返回 frozenset 集合，仅包含两端都是已知角色的联合对；
    无明确联合结构时返回空集（调用方走片段/全组合 fallback）。
    """
    pairs: set = set()
    for m in _ALLY_RE.finditer(sent):
        x, y = m.group(1), m.group(2)
        if x in names and y in names and x != y:
            pairs.add(frozenset((x, y)))
    for m in _ALLY_HUNT_RE.finditer(sent):
        y = m.group(1)
        if y not in names:
            continue
        head = sent[max(0, m.start() - 80):m.start()]
        cut = max(head.rfind(ch) for ch in "，,。；;！？")
        seg = head[cut + 1:] if cut >= 0 else head
        x = next((n for n in reversed(names)
                  if n and seg.rfind(n) >= 0 and seg.rfind(n) < len(seg)), None)
        if x is None:
            x = next((n for n in reversed(names) if n and head.rfind(n) >= 0), None)
        if x and x != y:
            pairs.add(frozenset((x, y)))
    return pairs


def _seg_role_sets(
    sent: str, names: List[str], kws: tuple,
) -> tuple:
    """按逗号片段收集：含任一关键词的片段角色集 与 其余片段角色集。

    返回 (hit_sets, other_sets, hit_segs)，其中 hit_segs 是含关键词片段的
    原文列表（供对抗动作词/被动标记判断）。
    """
    hit_sets: List[set] = []
    other_sets: List[set] = []
    hit_segs: List[str] = []
    for seg in _SEG_SPLIT_RE.split(sent):
        s = {n for n in names if n in seg}
        if not s:
            continue
        if any(k in seg for k in kws):
            hit_sets.append(s)
            hit_segs.append(seg)
        else:
            other_sets.append(s)
    return hit_sets, other_sets, hit_segs


def extract_relations(
    text: str, characters: List[es.Character],
) -> List[CharacterRelation]:
    """提取角色关系线（六类）。

    规则：叙述句中出现的已知角色名 >= 2 且命中关系线索词时生成关系；
    明确联合对（X与Y联手）优先限定同盟配对；无联合对时，
    对抗/同盟按逗号片段限定配对范围（对抗跨片段对立、同盟聚合亲和行为片段），
    减少一句多动词产生的误配；单角色 + 亲情称谓词时生成与「未命名亲属」的关系。
    """
    names = [c.name for c in characters if c.name not in _PROXY_NAMES]
    if not names:
        return []
    narration = re.sub(r"[“\"][^“”\"\n]{1,120}[”\"]", "", text)
    relations: List[CharacterRelation] = []
    seen: set = set()

    def _add(a: str, b: str, rel_type: str, sent: str) -> None:
        key = (a, b, rel_type)
        if key in seen:
            return
        seen.add(key)
        evidence = es.clip_line(sent, 40)
        relations.append(CharacterRelation(
            source=a, target=b, rel_type=rel_type, evidence=evidence,
        ))

    for sent in es._split_sentences(narration):
        sent_names = [n for n in names if n in sent]
        if not sent_names:
            continue
        ally_sets = {
            frozenset((m.group(1), m.group(2)))
            for m in _ALLY_RE.finditer(sent)
            if m.group(1) in names and m.group(2) in names
            and m.group(1) != m.group(2)
        }
        union_pairs = _union_pairs(sent, names)

        for rel_type, kws in _RELATION_RULES.items():
            if not any(k in sent for k in kws):
                continue
            if len(sent_names) >= 2:
                # 同盟类：明确联合对优先，只对联合对配对，
                # 避免同句的对抗对象（如被迎战的赵屠夫）被误配成同盟
                if rel_type == "同盟" and union_pairs:
                    for a, b in combinations(sent_names, 2):
                        if frozenset((a, b)) not in union_pairs:
                            continue
                        _add(a, b, rel_type, sent)
                    continue

                # 无明确联合对时，对抗/同盟按逗号片段限定配对
                hit_sets, other_sets, hit_segs = _seg_role_sets(
                    sent, names, kws)
                if rel_type == "同盟" and hit_sets:
                    # 同盟聚合亲和行为片段内角色
                    ally_names = sorted({n for s in hit_sets for n in s})
                    if len(ally_names) >= 2:
                        for a, b in combinations(ally_names, 2):
                            _add(a, b, rel_type, sent)
                        continue
                elif rel_type == "对抗" and hit_sets:
                    hit_names = {n for s in hit_sets for n in s}
                    other_names = {n for s in other_sets for n in s}
                    # 动作型对抗（含具体动作词或被动「被」）才有明确对立对象：
                    # 同一片段内互搏优先组合，跨片段施受再互补配对
                    has_action = any(
                        any(k in seg for k in _ACTION_CONFLICT_TERMS)
                        or "被" in seg
                        for seg in hit_segs
                    )
                    if has_action:
                        if len(hit_names) >= 2:
                            for a, b in combinations(sorted(hit_names), 2):
                                if frozenset((a, b)) in union_pairs:
                                    continue
                                _add(a, b, rel_type, sent)
                        if other_names:
                            for h in hit_names:
                                for o in other_names:
                                    if frozenset((h, o)) in union_pairs:
                                        continue
                                    _add(h, o, rel_type, sent)
                    else:
                        # 静态对抗词（仇/恨/怒/怨/敌/背叛…）无明确对立对象：
                        # 仅同一片段内出现多个角色时配对，避免「A发誓报仇」
                        # 把跨片段的 B 误配成对抗
                        if len(hit_names) >= 2:
                            for a, b in combinations(sorted(hit_names), 2):
                                _add(a, b, rel_type, sent)
                    continue

                # fallback：无法限定范围时按原有全组合配对
                for a, b in combinations(sent_names, 2):
                    if rel_type == "对抗" and frozenset((a, b)) in ally_sets:
                        continue
                    _add(a, b, rel_type, sent)
            elif len(sent_names) == 1 and rel_type == "亲情":
                term = next((k for k in _KINSHIP_TERMS if k in sent), "")
                if term:
                    _add(
                        sent_names[0], term, rel_type,
                        sent + "（亲属未命名）",
                    )
            # 单角色 + 对抗/主从/交易/爱慕：无第二角色时不臆造关系对象
    return relations


def summarize_relations(relations: List[CharacterRelation]) -> str:
    """生成人物关系摘要文本（用于角色 description 与展示）。"""
    if not relations:
        return ""
    parts: List[str] = []
    for rel in relations:
        parts.append(f"{rel.source}×{rel.target}（{rel.rel_type}）")
    return "；".join(parts)


def _describe_character(
    ch: es.Character, relations: List[CharacterRelation],
) -> es.Character:
    """更新角色一句话定位：保留 T07 定位，附加直接关联的关系线摘要（最多 2 条）。"""
    mine = [
        r for r in relations
        if ch.name in (r.source, r.target) and r.target not in _KINSHIP_TERMS
    ] or [
        r for r in relations if ch.name in (r.source, r.target)
    ]
    rel_text = "；".join(
        f"{r.source}×{r.target}（{r.rel_type}）" for r in mine[:2]
    )
    if rel_text:
        return es.Character(
            name=ch.name, role=ch.role,
            description=f"{ch.description}；{rel_text}",
        )
    return ch


# ------------------- 单集/全计划增强 -------------------


def enrich_episode(ep: es.Episode) -> es.Episode:
    """对 T07 单集做角色关系增强（就地修改并返回）。

    顺序：1) 清洗黑名单身份词角色；若无任何明确角色，先从纯叙述文本挖掘
    候选名并生成角色；2) 隔词/隔动作说话人归属，并把新发现的说话人补入
    角色清单；3) 提取关系线；4) 更新角色 description 附加关系摘要。
    """
    text = ep.source_text or ""

    # 清洗 T07 基础版可能误提的「声音」等身份词角色
    ep.characters = [
        c for c in ep.characters if c.name not in _NAME_BLACKLIST
    ]
    chars = list(ep.characters)
    known = [c.name for c in chars if c.name not in _PROXY_NAMES]

    if not known:
        discovered = discover_narration_names(text)
        if discovered:
            ep.characters = [
                es.Character(
                    name=name,
                    role="主角" if i == 0 else "配角",
                    description="由纯叙述主体推断（T08）",
                )
                for i, name in enumerate(discovered)
            ]
            known = list(discovered)

    ep.lines = assign_line_speakers(text, ep.lines, known)

    # 补充由说话短语发现的新角色（如「李强推开门，急切说道」中的李强）
    speakers = {ln.speaker for ln in ep.lines if ln.speaker != "旁白"}
    for sp in speakers:
        if not _candidate_ok(sp):
            continue
        if all(c.name != sp for c in ep.characters):
            role = (
                "主角"
                if all(c.name in _PROXY_NAMES for c in ep.characters)
                else "配角"
            )
            ep.characters.append(
                es.Character(
                    name=sp, role=role,
                    description="由台词说话人发现（T08）",
                )
            )

    # 已存在真实角色时移除 T07 占位「主角/配角」，避免与真名并存
    if any(c.name not in _PROXY_NAMES for c in ep.characters):
        ep.characters = [c for c in ep.characters if c.name not in _PROXY_NAMES]

    relations = extract_relations(text, ep.characters)
    ep.relations = [asdict(r) for r in relations]
    ep.characters = [_describe_character(c, relations) for c in ep.characters]
    return ep


def enrich_plan(plan: es.EpisodePlan) -> es.EpisodePlan:
    """对 T07 EpisodePlan 全量增强角色关系线（就地修改并返回）。"""
    for ep in plan.episodes:
        enrich_episode(ep)
    return plan


def build_enriched_plan(
    raw_text: str,
    template: Optional[str] = None,
    target_duration: int = es.DEFAULT_TARGET_DURATION,
    shots_per_minute: int = es.SHOTS_PER_MINUTE,
) -> es.EpisodePlan:
    """完整链路：T06 解析 -> T07 拆集 -> T08 角色关系增强。"""
    plan = es.split_episodes_from_text(
        raw_text, template=template,
        target_duration=target_duration, shots_per_minute=shots_per_minute,
    )
    return enrich_plan(plan)


# ------------------- 预留 T09/T10 衔接点 -------------------


def appearance_timeline(plan: es.EpisodePlan) -> Dict[str, List[int]]:
    """角色出场时间线（供 T09 钩子生成 / T10 导出使用）。

    返回 {角色名: 出场的集号列表}；角色出现与消失情况可用于剧情因果检查。
    """
    timeline: Dict[str, List[int]] = {}
    for ep in plan.episodes:
        for ch in ep.characters:
            if ch.name in _PROXY_NAMES:
                continue
            timeline.setdefault(ch.name, []).append(ep.episode)
    return timeline