# -*- coding: utf-8 -*-
"""T11-T15 分镜拆解器：把单集剧本拆成逐镜分镜表。

运镜与转场术语来自两份运镜资料与一份转场资料：
- 運鏡技巧（70 套运镜提示词、万能公式 6 要素、四大原则、词库）
- AI運鏡（六类运镜：推/拉/摇/移/跟/特殊，每类细分术语与适用情绪）
- 轉場技巧（10 大类 135 种转场、10 个通用转场公式）

设计要点：
- 输出兼容 es.Shot（镜号/景别/运镜/画面内容/台词/角色/情绪/表情/音调/时长），
  新增 camera_note（运镜细分术语）与 transition（转场方式）两个只读增强字段；
- camera 取值仍在 M0 六类枚举（固定/推/拉/摇/移/跟随）内，细分术语进 camera_note；
- 四大原则落地：情绪越强镜头越近、场面越大镜头越远、动作越快镜头越有方向、
  转场不乱用（同场景直接切，换场景才用穿越/甩镜/叠化类转场）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import episode_splitter as es


# ------------------- 运镜术语库 -------------------

# 六类运镜 -> 细分术语（来源：AI運鏡.pdf + 運鏡技巧.pdf）
CAMERA_LIBRARY: Dict[str, List[str]] = {
    "推": [
        "缓慢推近", "快速推镜", "从远景推至特写", "瞳孔放大推",
        "呼吸式推拉", "冲击推", "穿越推",
    ],
    "拉": [
        "缓慢拉远", "急速后拉", "人物变小拉", "展示环境拉",
        "转场拉", "真相揭示拉", "情绪抽离拉",
    ],
    "摇": [
        "横摇全景", "上下摇镜", "快速摇镜", "慢摇跟随",
        "摇至身后", "甩镜", "来回摇",
    ],
    "移": [
        "跟拍行走", "平行横移", "360度环绕", "滑轨平移",
        "穿越移", "弧形移", "上下升降移",
    ],
    "跟随": [
        "手持跟拍", "侧面跟拍", "背影跟拍", "正面跟拍",
        "加速跟拍", "第一人称跟拍", "低角度跟拍",
    ],
    "固定": ["固定机位"],
}

# 情绪 -> 运镜细分术语偏好（情绪越强镜头越推越近，公式/四大原则①）
_EMOTION_CAMERA_NOTE: Dict[str, str] = {
    "愤怒": "冲击推",
    "悲伤": "缓慢推近",
    "惊讶": "瞳孔放大推",
    "恐惧": "快速推镜",
    "喜悦": "缓慢推近",
    "冷漠": "固定机位",
    "紧张": "呼吸式推拉",
    "得意": "缓慢拉远",
    "专注": "缓慢推近",
    "迟疑": "呼吸式推拉",
    "平静": "固定机位",
}

# 情绪 -> 景别偏好（四大原则①：情绪越强镜头越近）
_EMOTION_SIZE: Dict[str, str] = {
    "愤怒": "特写",
    "悲伤": "特写",
    "惊讶": "近景",
    "恐惧": "特写",
    "喜悦": "近景",
    "冷漠": "中景",
    "紧张": "近景",
    "得意": "中景",
    "专注": "中景",
    "迟疑": "近景",
    "平静": "中景",
}

# 情绪 -> 运镜大类偏好（配合相机细分）
_EMOTION_CAMERA: Dict[str, str] = {
    "愤怒": "推",
    "悲伤": "推",
    "惊讶": "推",
    "恐惧": "推",
    "喜悦": "推",
    "冷漠": "固定",
    "紧张": "推",
    "得意": "拉",
    "专注": "推",
    "迟疑": "推",
    "平静": "固定",
}

# 场面规模词 -> 使用大景别（四大原则②：场面越大镜头越远）
_BIG_SCENE_KEYWORDS = [
    "战场", "宫殿", "云海", "城市", "宗门", "大军", "战场", "浩大",
    "壮阔", "广场", "群山", "大海", "战场", "军队", "万千",
]
_BIG_SCENE_SIZE = "远景"
_BIG_SCENE_CAMERA = "拉"

# 动作速度词 -> 镜头跟着动作走（四大原则③：动作越快镜头越有方向）
_ACTION_CAMERA_KEYWORDS = [
    "冲", "奔", "追", "逃", "跑", "跃", "跳", "闪", "挥", "劈",
    "刺", "斩", "躲", "疾", "加速", "坠落", "摔",
    "拔剑", "拔刀", "出手", "袭来", "扑来", "擒拿", "交锋", "撕打",
]
_ACTION_CAMERA = "跟随"
_ACTION_CAMERA_NOTE = "加速跟拍"


# ------------------- 转场术语库 -------------------

# 10 大类转场（来源：轉場技巧.pdf 10 大类 135 种转场）
TRANSITION_LIBRARY: Dict[str, List[str]] = {
    # 第 1 类：遮挡式（20 个）
    "遮挡式": [
        "镜面置换转场", "风雪覆盖转场", "黑帧切割转场", "书信启幕转场",
        "水波扩散转场", "窗帘拂过转场", "迷雾吞没转场", "玻璃起雾转场",
        "火焰蔓延转场", "物件掠镜转场", "衣袖拂镜转场", "人物横镜遮挡",
        "手掌遮镜转场", "门框隔景转场", "地图展开转场", "照片引渡转场",
        "雨幕遮挡转场", "花瓣飘落转场", "纸张翻动转场", "面具遮面转场",
    ],
    # 第 2 类：镜头运动（14 个）
    "镜头运动式": [
        "俯镜俯冲转场", "极速甩镜转场", "镜头下坠转场", "环绕旋镜转场",
        "侧移穿越转场", "抬镜升空转场", "镜头后退转场", "穿跨穿梭转场",
        "镜头上升转场", "推镜聚焦转场", "旋转镜头转场", "拉远叙事转场",
        "镜头贴近转场", "跟跑穿越转场",
    ],
    # 第 3 类：动作匹配（8 个）
    "动作匹配式": [
        "回身错位转场", "拔剑出鞘转场", "挥刀衔接转场", "腾空跃迁转场",
        "抬手召唤转场", "抬眸觉醒转场", "奔袭穿梭转场", "蹲下起身转场",
    ],
    # 第 4 类：奇幻叙事（6 个）
    "奇幻叙事式": [
        "闭眼睁眼转场", "起落时空转场", "伸手触碰转场", "物引引线转场",
        "转身回眸转场", "尾袖转身转场",
    ],
    # 第 5 类：光影氛围（14 个）
    "光影氛围式": [
        "月色漫染转场", "雷霆闪切转场", "霓虹闪烁转场", "日光过曝转场",
        "金色光芒转场", "烛焰侵染转场", "红色火光转场", "强光溢散转场",
        "烛光摇曳转场", "向光突围转场", "蓝色冷光转场", "烈焰焚境转场",
        "天光破晓转场", "幻彩光晕转场",
    ],
    # 第 6 类：时空流变（11 个）
    "时空流变式": [
        "四季更迭转场", "时间加速转场", "世代迭代转场", "回溯忆旧转场",
        "年岁更迭转场", "古物见证转场", "城建变迁转场", "昼夜流转转场",
        "器物岁月转场", "记忆闪回转场", "人物蜕变转场",
    ],
    # 第 7 类：空间跃迁（12 个）
    "空间跃迁式": [
        "深海冲天转场", "门后异境转场", "城郭升空转场", "洞穴穿行转场",
        "林莽入战转场", "镜中世界转场", "云巅赴阙转场", "传送门转场",
        "实境陷幻境转场", "画中世界转场", "室宇向外转场", "地裂陷落转场",
    ],
    # 第 8 类：电影高级叙事（12 个）
    "电影高级叙事式": [
        "双线平行转场", "视线引导转场", "蒙太奇岁月转场", "遮挡物匹配转场",
        "长镜连贯叙事", "虚实景深转场", "声音先行转场", "穿廊长镜转场",
        "图形匹配转场", "动作残影转场", "环境遮切转场", "收束片尾转场",
    ],
    # 第 9 类：开篇式（12 个）
    "开篇式": [
        "电影现身开篇", "异象降临开篇", "瞳眸苏醒开篇", "战场残响开篇",
        "雨幕登场开篇", "破碎开场", "重门启幕开篇", "梦境预警开篇",
        "背影揭面开篇", "废墟涅槃开篇", "兵器先导开篇", "高台俯临开篇",
    ],
}

# 10 个通用转场公式（转场不乱用原则下的"换场景"优先选项）
TRANSITION_FORMULAS: List[str] = [
    "情绪引爆高潮式", "人物动作驱动式", "梦境现实切换式", "光效带动情绪式",
    "空间穿越拼接式", "前景遮掩切换式", "岁月成长递进式", "道具线索串联式",
    "环境递进叙事式", "电影级万能拼接公式",
]

# 集末钩子类型 -> 收尾转场（轉場技巧.pdf 通用公式/"收束片尾"族中最贴合的）
_HOOK_TRANSITION: Dict[str, str] = {
    "悬念": "拉远叙事转场",
    "反转": "书信启幕转场",
    "危机": "黑帧切割转场",
    "新信息": "声音先行转场",
}

# 情绪词 -> 情绪（从台词/旁白/核心冲突中抽取主角情绪）
_EMOTION_KEYWORDS: List[Tuple[str, str]] = [
    ("怒", "愤怒"), ("气", "愤怒"), ("恨", "愤怒"), ("咬牙", "愤怒"),
    ("哭", "悲伤"), ("泪", "悲伤"), ("伤心", "悲伤"), ("难过", "悲伤"), ("痛", "悲伤"),
    ("惊", "惊讶"), ("没想到", "惊讶"), ("意外", "惊讶"),
    ("怕", "恐惧"), ("慌", "恐惧"), ("恐怖", "恐惧"), ("颤抖", "恐惧"),
    ("笑", "喜悦"), ("高兴", "喜悦"), ("喜", "喜悦"), ("激动", "喜悦"),
    ("冷", "冷漠"), ("漠", "冷漠"), ("无动于衷", "冷漠"),
    ("紧张", "紧张"), ("握紧", "紧张"), ("着急", "紧张"),
    ("得意", "得意"), ("冷笑", "得意"), ("骄傲", "得意"),
    ("专注", "专注"), ("凝视", "专注"), ("盯着", "专注"), ("集中", "专注"),
    ("犹豫", "迟疑"), ("迟疑", "迟疑"), ("沉默", "迟疑"),
]

# 转场场景词 -> 具体转场（来源：轉場技巧.pdf 每个转场标注的"适用"场景）。
# 顺序即优先级：先命中的更具体转场词优先，未命中走大类兜底。
_TRANSITION_SCENE_RULES: List[Tuple[str, str]] = [
    # 遮挡式（20 个）
    ("穿越", "镜面置换转场"),
    ("平行世界", "镜面置换转场"),
    ("幻境", "镜面置换转场"),
    ("离别", "风雪覆盖转场"),
    ("边关", "风雪覆盖转场"),
    ("命运转折", "风雪覆盖转场"),
    ("冬季", "风雪覆盖转场"),
    ("高潮", "黑帧切割转场"),
    ("强冲突", "黑帧切割转场"),
    ("章节", "黑帧切割转场"),
    ("回忆", "书信启幕转场"),
    ("真相", "书信启幕转场"),
    ("伏笔", "书信启幕转场"),
    ("潜入", "水波扩散转场"),
    ("情感转折", "水波扩散转场"),
    ("梦境", "窗帘拂过转场"),
    ("秘密空间", "窗帘拂过转场"),
    ("秘境", "迷雾吞没转场"),
    ("仙侠", "迷雾吞没转场"),
    ("窥探", "玻璃起雾转场"),
    ("悬疑", "玻璃起雾转场"),
    ("心理", "玻璃起雾转场"),
    ("重生", "火焰蔓延转场"),
    ("高燃", "火焰蔓延转场"),
    ("地点跳转", "物件掠镜转场"),
    ("道具推进", "物件掠镜转场"),
    ("瞬移", "衣袖拂镜转场"),
    ("身份互换", "人物横镜遮挡"),
    ("双线叙事", "人物横镜遮挡"),
    ("记忆闪回", "手掌遮镜转场"),
    ("内心视角", "手掌遮镜转场"),
    ("密室", "门框隔景转场"),
    ("府邸", "门框隔景转场"),
    ("空间进出", "门框隔景转场"),
    ("冒险", "地图展开转场"),
    ("战争部署", "地图展开转场"),
    ("羁绊", "照片引渡转场"),
    ("旧线回收", "照片引渡转场"),
    ("虐恋", "雨幕遮挡转场"),
    ("雨夜", "雨幕遮挡转场"),
    ("爱情", "花瓣飘落转场"),
    ("情绪过渡", "花瓣飘落转场"),
    ("日记", "纸张翻动转场"),
    ("线索推进", "纸张翻动转场"),
    ("黑化", "面具遮面转场"),
    ("身份隐藏", "面具遮面转场"),
    ("人物登场", "人物横镜遮挡"),
    ("身份揭晓", "人物横镜遮挡"),
    # 镜头运动（14 个）
    ("危机降临", "俯镜俯冲转场"),
    ("宏大视角", "俯镜俯冲转场"),
    ("开篇", "俯镜俯冲转场"),
    ("打斗", "极速甩镜转场"),
    ("紧张冲突", "极速甩镜转场"),
    ("追逐", "极速甩镜转场"),
    ("噩梦", "镜头下坠转场"),
    ("坠入", "镜头下坠转场"),
    ("力量觉醒", "环绕旋镜转场"),
    ("角色爆发", "环绕旋镜转场"),
    ("高光", "环绕旋镜转场"),
    ("城市穿行", "侧移穿越转场"),
    ("空间转换", "侧移穿越转场"),
    ("飞升", "抬镜升空转场"),
    ("世界观展开", "抬镜升空转场"),
    ("物是人非", "镜头后退转场"),
    ("异空间", "穿跨穿梭转场"),
    ("情绪升华", "镜头上升转场"),
    ("内心揭示", "推镜聚焦转场"),
    ("线索特写", "推镜聚焦转场"),
    ("精神世界", "旋转镜头转场"),
    ("时空跨度", "拉远叙事转场"),
    ("历史回溯", "拉远叙事转场"),
    ("宏大叙事", "拉远叙事转场"),
    ("压迫感", "镜头贴近转场"),
    ("逃亡", "跟跑穿越转场"),
    ("逃出", "跟跑穿越转场"),
    ("追兵", "跟跑穿越转场"),
    ("封锁", "环境遮切转场"),
    ("陷阱", "黑帧切割转场"),
    ("追踪", "跟跑穿越转场"),
    ("寻找目标", "跟跑穿越转场"),
    # 动作匹配（8 个）
    ("人物蜕变", "回身错位转场"),
    ("古今", "回身错位转场"),
    ("武侠", "拔剑出鞘转场"),
    ("战争", "挥刀衔接转场"),
    ("法术传送", "腾空跃迁转场"),
    ("力量觉醒", "抬手召唤转场"),
    ("顿悟", "抬眸觉醒转场"),
    ("立场转变", "抬眸觉醒转场"),
    ("赶路", "奔袭穿梭转场"),
    ("探索", "蹲下起身转场"),
    ("地下空间", "蹲下起身转场"),
    # 奇幻叙事（6 个）
    ("入梦", "闭眼睁眼转场"),
    ("时间流逝", "起落时空转场"),
    ("人物成长", "起落时空转场"),
    ("触发机关", "伸手触碰转场"),
    ("记忆同步", "伸手触碰转场"),
    ("命运连接", "伸手触碰转场"),
    ("伏笔回收", "物引引线转场"),
    ("命运相遇", "转身回眸转场"),
    ("权谋", "尾袖转身转场"),
    ("神秘退场", "尾袖转身转场"),
    # 光影氛围（14 个）
    ("思念", "月色漫染转场"),
    ("深夜", "月色漫染转场"),
    ("斗法", "雷霆闪切转场"),
    ("灾难", "雷霆闪切转场"),
    ("赛博", "霓虹闪烁转场"),
    ("都市", "霓虹闪烁转场"),
    ("治愈", "日光过曝转场"),
    ("清晨", "日光过曝转场"),
    ("神圣", "金色光芒转场"),
    ("命运开启", "金色光芒转场"),
    ("书房", "烛焰侵染转场"),
    ("毁灭", "红色火光转场"),
    ("爆发", "红色火光转场"),
    ("爆炸", "强光溢散转场"),
    ("回忆浮现", "强光溢散转场"),
    ("秘密谈话", "烛光摇曳转场"),
    ("救赎", "向光突围转场"),
    ("走出低谷", "向光突围转场"),
    ("心理压迫", "蓝色冷光转场"),
    ("浴火重生", "烈焰焚境转场"),
    ("希望", "天光破晓转场"),
    ("魔法世界", "幻彩光晕转场"),
    # 时空流变（11 个）
    ("漫长回忆", "四季更迭转场"),
    ("蒙太奇", "时间加速转场"),
    ("城市变迁", "时间加速转场"),
    ("文明变迁", "世代迭代转场"),
    ("回忆杀", "回溯忆旧转场"),
    ("一生叙事", "年岁更迭转场"),
    ("宿命", "年岁更迭转场"),
    ("传承", "古物见证转场"),
    ("家族故事", "古物见证转场"),
    ("宏大开篇", "城建变迁转场"),
    ("世界观铺垫", "城建变迁转场"),
    ("心境变化", "昼夜流转转场"),
    ("剧情推进", "昼夜流转转场"),
    ("时代更替", "器物岁月转场"),
    ("家族传承", "器物岁月转场"),
    ("觉醒", "记忆闪回转场"),
    ("失忆", "记忆闪回转场"),
    ("逆袭", "人物蜕变转场"),
    # 空间跃迁（12 个）
    ("自由感", "深海冲天转场"),
    ("新世界", "门后异境转场"),
    ("开篇", "城郭升空转场"),
    ("城市展示", "城郭升空转场"),
    ("探险", "洞穴穿行转场"),
    ("新地域", "洞穴穿行转场"),
    ("行军", "林莽入战转场"),
    ("埋伏", "林莽入战转场"),
    ("镜像", "镜中世界转场"),
    ("山门", "云巅赴阙转场"),
    ("圣地", "云巅赴阙转场"),
    ("空间跳跃", "传送门转场"),
    ("传送", "传送门转场"),
    ("试炼", "实境陷幻境转场"),
    ("法术幻境", "实境陷幻境转场"),
    ("画中", "画中世界转场"),
    ("日常冒险", "室宇向外转场"),
    ("地下探索", "地裂陷落转场"),
    # 电影高级叙事（12 个）
    ("命运对照", "双线平行转场"),
    ("视线引导", "视线引导转场"),
    ("大跨度成长", "蒙太奇岁月转场"),
    ("视觉呼应", "遮挡物匹配转场"),
    ("高级剪辑", "遮挡物匹配转场"),
    ("沉浸式", "长镜连贯叙事"),
    ("柔和", "虚实景深转场"),
    ("声音", "声音先行转场"),
    ("史诗", "穿廊长镜转场"),
    ("图形", "图形匹配转场"),
    ("快速移动", "动作残影转场"),
    ("能力者", "动作残影转场"),
    ("多场景", "环境遮切转场"),
    ("城市群像", "环境遮切转场"),
    ("收尾", "收束片尾转场"),
    ("故事收尾", "收束片尾转场"),
    ("章节落幕", "收束片尾转场"),
]


def _pick_transition_for_scene(scene_text: str) -> str:
    """换场景时按"适用场景"关键词选具体转场（转场不乱用）。"""
    for kw, trans in _TRANSITION_SCENE_RULES:
        if kw in scene_text:
            return trans
    # 未命中场景词：按通用公式的第 5 条（空间穿越拼接式）作电影感兜底
    return TRANSITION_FORMULAS[4]


# =================== 英文模式（输入英文 -> 输出英文） ===================

CAMERA_LIBRARY_EN: Dict[str, List[str]] = {
    "Push in": [
        "slow push in", "fast push", "push from wide to close-up",
        "pupil zoom push", "breathing push-pull", "impact push", "through push",
    ],
    "Pull back": [
        "slow pull back", "fast pull away", "character shrinks pull",
        "environment reveal pull", "transition pull", "truth reveal pull",
        "emotional detach pull",
    ],
    "Pan": [
        "panoramic pan", "vertical tilt pan", "quick whip pan",
        "slow follow pan", "pan to behind", "whip pan", "back and forth pan",
    ],
    "Tilt": [
        "low tilt up", "high tilt down", "dutch tilt", "orbit tilt",
    ],
    "Track": [
        "handheld track", "side track", "back follow track", "front follow track",
        "accelerate track", "first-person track", "low angle track",
    ],
    "Static": ["fixed camera"],
}

_EMOTION_CAMERA_NOTE_EN: Dict[str, str] = {
    "Angry": "impact push",
    "Sad": "slow push in",
    "Surprised": "pupil zoom push",
    "Afraid": "fast push",
    "Happy": "slow push in",
    "Indifferent": "fixed camera",
    "Tense": "breathing push-pull",
    "Proud": "slow pull back",
    "Focused": "slow push in",
    "Hesitant": "breathing push-pull",
    "Calm": "fixed camera",
}

_EMOTION_SIZE_EN: Dict[str, str] = {
    "Angry": "Close-up",
    "Sad": "Close-up",
    "Surprised": "Close-up",
    "Afraid": "Close-up",
    "Happy": "Medium",
    "Indifferent": "Medium",
    "Tense": "Close-up",
    "Proud": "Medium",
    "Focused": "Medium",
    "Hesitant": "Close-up",
    "Calm": "Medium",
}

_EMOTION_CAMERA_EN: Dict[str, str] = {
    "Angry": "Push in",
    "Sad": "Push in",
    "Surprised": "Push in",
    "Afraid": "Push in",
    "Happy": "Push in",
    "Indifferent": "Static",
    "Tense": "Push in",
    "Proud": "Pull back",
    "Focused": "Push in",
    "Hesitant": "Push in",
    "Calm": "Static",
}

_BIG_SCENE_KEYWORDS_EN = [
    "battlefield", "battle", "palace", "city", "army", "crowd", "square",
    "mountain", "sea", "ocean", "vast", "war", "kingdom", "desert", "plaza",
    "millions",
]
_BIG_SCENE_SIZE_EN = "Wide"
_BIG_SCENE_CAMERA_EN = "Pull back"

_ACTION_CAMERA_KEYWORDS_EN = [
    "run", "running", "chase", "chasing", "jump", "jumping", "flee", "fleeing",
    "escape", "dash", "rush", "stab", "slash", "punch", "kick", "fight",
    "fall", "falling", "accelerate", "dodge", "leap",
]
_ACTION_CAMERA_EN = "Track"
_ACTION_CAMERA_NOTE_EN = "accelerate track"

TRANSITION_LIBRARY_EN: Dict[str, List[str]] = {
    "Occlusion": [
        "mirror swap transition", "snow cover transition", "black frame cut",
        "letter reveal transition", "ripple transition", "curtain sweep transition",
        "fog swallow transition", "glass fog transition", "flame spread transition",
        "object flash transition", "hand cover transition", "door frame transition",
        "map unfold transition", "photo lead transition", "rain curtain transition",
        "petal fall transition", "page flip transition", "mask cover transition",
    ],
    "Camera Move": [
        "dive shot transition", "whip pan transition", "camera drop transition",
        "orbit transition", "side pass transition", "crane up transition",
        "camera pull transition", "pierce through transition", "camera rise transition",
        "focus push transition", "rotating camera transition", "wide reveal transition",
        "closing-in transition", "run-through transition",
    ],
    "Action Match": [
        "turn back match transition", "sword draw transition", "blade link transition",
        "jump cut transition", "hand raise transition", "eye open transition",
        "rush through transition", "crouch stand transition",
    ],
    "Light & Mood": [
        "moonlight wash transition", "thunder flash transition", "neon flicker transition",
        "sunlight overexposure transition", "golden glow transition",
        "candle flame transition", "red fire transition", "light burst transition",
        "candle sway transition", "cold blue light transition", "flame burn transition",
        "dawn light transition", "color glow transition",
    ],
    "Time & Space": [
        "season change transition", "time lapse transition", "era shift transition",
        "memory flashback transition", "year pass transition", "relic witness transition",
        "city change transition", "day night cycle transition", "object age transition",
        "memory flash transition", "character transform transition",
    ],
    "Space Jump": [
        "deep sea surge transition", "portal transition", "mirror world transition",
        "cloud ascent transition", "cave pass transition", "forest to war transition",
        "painting world transition", "space warp transition",
    ],
    "Narrative": [
        "parallel cut transition", "gaze guide transition", "montage transition",
        "match cut transition", "long take narrative", "depth of field transition",
        "sound first transition", "graphic match transition", "motion blur transition",
        "environment wipe transition", "ending wrap transition",
    ],
    "Opening": [
        "movie reveal opening", "omen arrival opening", "eye awakening opening",
        "battle echo opening", "rain curtain opening", "broken opening",
        "gate open opening", "dream warning opening", "back reveal opening",
        "ashes rebirth opening", "weapon lead opening", "high platform opening",
    ],
}

TRANSITION_FORMULAS_EN: List[str] = [
    "climax burst formula", "character action formula", "dream reality switch formula",
    "light mood formula", "space passage formula", "foreground wipe formula",
    "growth progression formula", "prop clue formula", "environment narrative formula",
    "cinematic universal formula",
]

# 英文场景词 -> 具体英文转场（顺序即优先级；值必须都在 TRANSITION_LIBRARY_EN）
_TRANSITION_SCENE_RULES_EN: List[Tuple[str, str]] = [
    ("portal", "portal transition"), ("teleport", "portal transition"),
    ("dimension", "portal transition"), ("parallel world", "mirror world transition"),
    ("illusion", "mirror world transition"), ("mirror", "mirror world transition"),
    ("flashback", "memory flashback transition"), ("memory", "memory flash transition"),
    ("memories", "memory flash transition"), ("remember", "memory flash transition"),
    ("truth", "letter reveal transition"), ("secret", "letter reveal transition"),
    ("letter", "letter reveal transition"), ("confession", "letter reveal transition"),
    ("dream", "curtain sweep transition"), ("nightmare", "camera drop transition"),
    ("climax", "black frame cut"), ("crisis", "black frame cut"),
    ("danger", "black frame cut"), ("trap", "black frame cut"),
    ("fight", "whip pan transition"), ("battle", "blade link transition"),
    ("chase", "run-through transition"), ("escape", "run-through transition"),
    ("flee", "run-through transition"), ("run away", "run-through transition"),
    ("city", "environment wipe transition"), ("urban", "neon flicker transition"),
    ("rebellious", "neon flicker transition"),
    ("rain", "rain curtain transition"), ("storm", "thunder flash transition"),
    ("thunder", "thunder flash transition"), ("lightning", "thunder flash transition"),
    ("love", "petal fall transition"), ("romantic", "petal fall transition"),
    ("departure", "snow cover transition"), ("farewell", "snow cover transition"),
    ("winter", "snow cover transition"),
    ("awakening", "eye open transition"), ("power", "hand raise transition"),
    ("strength", "hand raise transition"),
    ("rebirth", "flame spread transition"), ("fire", "flame spread transition"),
    ("burn", "flame burn transition"), ("explosion", "light burst transition"),
    ("time", "time lapse transition"), ("years", "season change transition"),
    ("aging", "year pass transition"),
    ("war", "map unfold transition"), ("army", "map unfold transition"),
    ("battlefield", "dive shot transition"),
    ("underworld", "deep sea surge transition"), ("sea", "deep sea surge transition"),
    ("ocean", "deep sea surge transition"),
    ("cave", "cave pass transition"), ("underground", "cave pass transition"),
    ("identity", "mask cover transition"), ("disguise", "mask cover transition"),
    ("hidden", "mask cover transition"),
    ("ending", "ending wrap transition"), ("final", "ending wrap transition"),
    ("dawn", "dawn light transition"), ("morning", "sunlight overexposure transition"),
    ("night", "moonlight wash transition"), ("midnight", "moonlight wash transition"),
    ("suspense", "glass fog transition"), ("psychological", "glass fog transition"),
]

_HOOK_TRANSITION_EN: Dict[str, str] = {
    "Suspense": "wide reveal transition",
    "Twist": "letter reveal transition",
    "Crisis": "black frame cut",
    "New Info": "sound first transition",
}

_EMOTION_KEYWORDS_EN: List[Tuple[str, str]] = [
    ("angry", "Angry"), ("rage", "Angry"), ("fury", "Angry"), ("clench", "Angry"),
    ("hate", "Angry"), ("irritated", "Angry"),
    ("cry", "Sad"), ("tears", "Sad"), ("sad", "Sad"), ("grief", "Sad"),
    ("hurt", "Sad"), ("heartbroken", "Sad"), ("sob", "Sad"),
    ("surprised", "Surprised"), ("shock", "Surprised"), ("unexpected", "Surprised"),
    ("astonished", "Surprised"), ("amazed", "Surprised"),
    ("afraid", "Afraid"), ("fear", "Afraid"), ("panic", "Afraid"), ("tremble", "Afraid"),
    ("terrified", "Afraid"), ("scared", "Afraid"),
    ("smile", "Happy"), ("happy", "Happy"), ("joy", "Happy"), ("excited", "Happy"),
    ("grin", "Happy"), ("laugh", "Happy"),
    ("cold", "Indifferent"), ("indifferent", "Indifferent"), ("emotionless", "Indifferent"),
    ("unmoved", "Indifferent"), ("flat", "Indifferent"),
    ("nervous", "Tense"), ("tense", "Tense"), ("grip", "Tense"), ("urgent", "Tense"),
    ("anxious", "Tense"), ("sweat", "Tense"),
    ("proud", "Proud"), ("smirk", "Proud"), ("arrogant", "Proud"), ("pride", "Proud"),
    ("focus", "Focused"), ("stare", "Focused"), ("staring", "Focused"),
    ("concentrate", "Focused"), ("gaze", "Focused"),
    ("hesitate", "Hesitant"), ("hesitant", "Hesitant"), ("silence", "Hesitant"),
    ("hesitation", "Hesitant"), ("pause", "Hesitant"),
]

_HOOK_EMOTION_EN: Dict[str, str] = {
    "Suspense": "Hesitant",
    "Twist": "Surprised",
    "Crisis": "Afraid",
    "New Info": "Focused",
}

_PROGRESS_EMOTION_EN: List[Tuple[float, str]] = [
    (0.00, "Calm"),
    (0.20, "Focused"),
    (0.40, "Tense"),
    (0.60, "Angry"),
    (0.85, "Surprised"),
]

_LOW_EMOTIONS_EN = {"Calm", "Indifferent", "Focused", "Hesitant"}
_HIGH_EMOTIONS_EN = {"Angry", "Afraid", "Surprised", "Sad"}
_MID_TRANSITION_FALLBACK_EN = "focus push transition"


def _clip_en(text: str, max_words: int = 30) -> str:
    """英文模式截断画面描述到合理长度（按词数，优先在句末标点处截断）。"""
    text = text.strip()
    words = text.split()
    if len(words) <= max_words:
        return text
    head = words[:max_words]
    cut = -1
    for i in range(len(head) - 1, -1, -1):
        if head[i].endswith((".", "!", "?")):
            cut = i
            break
    if cut >= 6:
        return " ".join(head[: cut + 1])
    return " ".join(head) + "…"


def _detect_emotion_en(text: str) -> str:
    if not text:
        return "Calm"
    lower = text.lower()
    for kw, emo in _EMOTION_KEYWORDS_EN:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return emo
    return "Calm"


def _is_big_scene_en(text: str) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", lower)
               for kw in _BIG_SCENE_KEYWORDS_EN)


def _has_fast_action_en(text: str) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", lower)
               for kw in _ACTION_CAMERA_KEYWORDS_EN)


def _pick_camera_en(emotion: str, text: str) -> Tuple[str, str]:
    if _has_fast_action_en(text):
        return _ACTION_CAMERA_EN, _ACTION_CAMERA_NOTE_EN
    if _is_big_scene_en(text):
        return _BIG_SCENE_CAMERA_EN, "environment reveal pull"
    camera = _EMOTION_CAMERA_EN.get(emotion, "Static")
    note = _EMOTION_CAMERA_NOTE_EN.get(emotion, "fixed camera")
    return camera, note


def _pick_size_en(emotion: str, text: str) -> str:
    if _is_big_scene_en(text):
        return _BIG_SCENE_SIZE_EN
    return _EMOTION_SIZE_EN.get(emotion, "Medium")


def _pick_transition_for_scene_en(scene_text: str) -> str:
    lower = scene_text.lower()
    for kw, trans in _TRANSITION_SCENE_RULES_EN:
        if kw in lower:
            return trans
    return TRANSITION_FORMULAS_EN[4]


def _pick_hook_transition_en(hook_type: str) -> str:
    return _HOOK_TRANSITION_EN.get(hook_type, "wide reveal transition")


def _progress_emotion_en(pos: float, hook_type: str) -> str:
    cur = "Calm"
    for start, emo in _PROGRESS_EMOTION_EN:
        if pos >= start:
            cur = emo
    if pos >= 0.92:
        cur = _HOOK_EMOTION_EN.get(hook_type, "Hesitant")
    return cur


def _pick_mid_transition_en(text: str, prev_emotion: str,
                            cur_emotion: str) -> str:
    if prev_emotion in _LOW_EMOTIONS_EN and cur_emotion in _HIGH_EMOTIONS_EN:
        chosen = _pick_transition_for_scene_en(text)
        if chosen == TRANSITION_FORMULAS_EN[4]:
            return _MID_TRANSITION_FALLBACK_EN
        return chosen
    return ""


def _dialog_plain_en(dialogue: Optional[str]) -> str:
    """把「[角色] \"内容\"」转为「角色: \"内容\"」。"""
    if not dialogue:
        return ""
    s = dialogue.strip()
    m = re.match(r"^\[([^\]]+)\]\s*(\".*?\")$", s)
    if m:
        return f"{m.group(1)}: {m.group(2)}"
    return s


# ------------------- 数据类 -------------------


@dataclass
class StoryboardShot(es.Shot):
    """分镜表一行：M0 十字段 + 运镜细分术语 + 转场方式。

    camera_note 只读增强：不参与 es.validate_plan 的枚举校验；
    transition 只读增强：记录"上一镜 -> 本镜"的转场方式，首镜为空。
    """
    camera_note: str = ""
    transition: str = ""


# ------------------- 小工具 -------------------


def _clip(text: str, max_len: int = 60) -> str:
    """截断画面描述到合理长度，优先在标点处断句。"""
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut_at = max(text.rfind("。"), text.rfind("！"), text.rfind("？"),
                 text.rfind("，"), text.rfind("；"))
    if cut_at >= 12:
        return text[: cut_at + 1]
    return text[: max_len] + "……"


def _detect_emotion(text: str) -> str:
    """从一段文本里抽取主角情绪（默认平静）。"""
    if not text:
        return "平静"
    for kw, emo in _EMOTION_KEYWORDS:
        if kw in text:
            return emo
    return "平静"


def _is_big_scene(text: str) -> bool:
    return any(kw in text for kw in _BIG_SCENE_KEYWORDS)


def _has_fast_action(text: str) -> bool:
    return any(kw in text for kw in _ACTION_CAMERA_KEYWORDS)


def _pick_camera(emotion: str, text: str) -> Tuple[str, str]:
    """选择运镜大类 + 细分术语（四大原则驱动）。"""
    if _has_fast_action(text):
        return _ACTION_CAMERA, _ACTION_CAMERA_NOTE
    if _is_big_scene(text):
        return _BIG_SCENE_CAMERA, "展示环境拉"
    camera = _EMOTION_CAMERA.get(emotion, "固定")
    note = _EMOTION_CAMERA_NOTE.get(emotion, "固定机位")
    return camera, note


def _pick_size(emotion: str, text: str) -> str:
    """选择景别（四大原则①②）。"""
    if _is_big_scene(text):
        return _BIG_SCENE_SIZE
    return _EMOTION_SIZE.get(emotion, "中景")


def _pick_hook_transition(hook_type: str) -> str:
    return _HOOK_TRANSITION.get(hook_type, "拉远叙事转场")


# 叙事节奏曲线：按镜头进度在文本无情绪词时给出情绪铺垫（M0：镜序遵循叙事节奏）
# (进度下限, 情绪)；收尾段按钩子类型收束
_PROGRESS_EMOTION: List[Tuple[float, str]] = [
    (0.00, "平静"),   # 铺垫
    (0.20, "专注"),   # 进入情境
    (0.40, "紧张"),   # 逼近冲突
    (0.60, "愤怒"),   # 冲突爆发
    (0.85, "惊讶"),   # 转折/新信息
]

# 钩子类型 -> 集末镜情绪（与 _HOOK_TRANSITION 配套）
_HOOK_EMOTION: Dict[str, str] = {
    "悬念": "迟疑",
    "反转": "惊讶",
    "危机": "恐惧",
    "新信息": "专注",
}

# 情绪强度跃升（用于同场景中段"情绪拐点转场"，营造画面转换节奏）
_LOW_EMOTIONS = {"平静", "冷漠", "专注", "迟疑"}
_HIGH_EMOTIONS = {"愤怒", "恐惧", "惊讶", "悲伤"}
_MID_TRANSITION_FALLBACK = "推镜聚焦转场"  # 镜头运动式：推进感强、可搭情绪逼近


def _split_sentences(text: Optional[str]) -> List[str]:
    """按中文句读拆分叙事文本（。！？；换行），保留原句，去空句。"""
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[。！？；\n])", text) if p.strip()]
    return parts


def _progress_emotion(pos: float, hook_type: str) -> str:
    """按镜头进度生成情绪（文本无词可命中时的叙事节奏兜底）。"""
    cur = "平静"
    for start, emo in _PROGRESS_EMOTION:
        if pos >= start:
            cur = emo
    if pos >= 0.92:
        cur = _HOOK_EMOTION.get(hook_type, "迟疑")
    return cur


def _pick_mid_transition(text: str, prev_emotion: str, cur_emotion: str) -> str:
    """情绪拐点转场：情绪强度从低跃升到高时返回具体转场，否则空串。

    转场不乱用——只有情绪明显转折才插入，未命中场景词时用镜头运动式兜底。
    """
    if prev_emotion in _LOW_EMOTIONS and cur_emotion in _HIGH_EMOTIONS:
        chosen = _pick_transition_for_scene(text)
        # 场景规则兜底（空间穿越拼接式）不适合情绪拐点，换推进式镜头转场
        if chosen == TRANSITION_FORMULAS[4]:
            return _MID_TRANSITION_FALLBACK
        return chosen
    return ""


# ------------------- 单集分镜拆解 -------------------


def storyboard_episode(ep: es.Episode) -> List[StoryboardShot]:
    """把单集拆成逐镜分镜表（T11-T13 核心）。

    输入消费 T07/T08 的 Episode：lines（台词/旁白）、scenes（场景）、
    characters（角色）、core_conflict、episode_hook、hook_type、source_text。

    规则：
    - 镜头数按 3 秒/镜公式，密度 18--22 镜/分钟（T12，与 es 一致）；
    - 叙事来源优先 source_text 按句切分：T07 常把整段原文压成 1 条旁白，
      这里还原成逐镜推进的叙事单元，保证画面内容、情绪、景别逐镜变化；
    - 台词逐字保留（M0：台词与旁白与剧本逐字一致），无台词镜头 dialogue 留空；
    - 情绪：文本命中情绪词优先；无词可命中时按叙事节奏曲线推进，
      集末镜按钩子类型收束（M0：镜序遵循叙事节奏）；
    - 首镜开篇用"开篇式"转场；同场景连续镜不转场（转场不乱用）；
      换场景用遮挡/镜头运动/光影/时空/空间类转场；情绪拐点用推进式转场；
      集末镜用钩子类型匹配的收尾转场（转场镜头用远景，M0 规则 7）；
    - 冲突镜用近景/特写与短镜头，画面内容一镜一个动作、位置明确。
    """
    n = max(1, round(ep.target_duration * es.SHOTS_PER_MINUTE / 60))
    n = max(n, (ep.target_duration + es.SHOT_MAX_DURATION - 1)
            // es.SHOT_MAX_DURATION)
    n = min(n, ep.target_duration // es.SHOT_MIN_DURATION)
    base, rem = divmod(ep.target_duration, n)
    durations = [base + (1 if i < rem else 0) for i in range(n)]

    en = getattr(ep, "language", "zh") == "en"
    lines = ep.lines or []
    scenes = ep.scenes or []
    chars = ep.characters or []
    lead = chars[0].name if chars else ("Protagonist" if en else "主角")
    conflict = ep.core_conflict or ""
    hook = ep.episode_hook or ""
    hook_type = ep.hook_type or ("Suspense" if en else "悬念")
    source = ep.source_text or conflict or ""
    narrator_name = "Narrator" if en else "旁白"

    # 按语言切句：英文按句点/问号/感叹号；中文按句读标点
    def split_sents(t: Optional[str]) -> List[str]:
        if en:
            return es._split_sentences_lang(t, "en")
        return _split_sentences(t)

    # 叙事单元：尽量用完整素材切句还原（T07 压缩后的 lines 文本也并入）
    narratives_raw = split_sents(source)
    if len(narratives_raw) < 2:
        narratives_raw = split_sents(conflict) + split_sents(hook)
    if not narratives_raw:
        narratives_raw = [conflict or ("advance the plot" if en else "推进剧情")]
    narratives: List[Tuple[str, str]] = [(s, narrator_name) for s in narratives_raw]
    # 台词集合：多行 lines 逐字取（保留讲话人）；单条旁白时若源文本完整
    # 叙事有多句，直接用源文本句子做旁白（逐字保留原文），否则用该旁白切句
    speech_pool: List[Tuple[str, str]] = []  # (文本, 讲话人)
    if len(lines) >= 2:
        speech_pool = [(ln.text, ln.speaker) for ln in lines if ln.text.strip()]
    elif len(lines) == 1:
        src_sents = split_sents(source)
        if len(src_sents) > 1:
            speech_pool = [(s, lines[0].speaker) for s in src_sents]
        else:
            speech_pool = [(s, lines[0].speaker)
                           for s in (split_sents(lines[0].text) or [lines[0].text])]

    def item_for(pool: List[Tuple[str, str]], i: int) -> Optional[Tuple[str, str]]:
        if not pool:
            return None
        idx = min(len(pool) - 1, round(i * len(pool) / n))
        return pool[idx]

    # 场景：按镜头比例把场景序列铺开，用于确定"是否换场景"与转场词
    scene_seq: List[Optional[es.Scene]] = []
    if scenes:
        for i in range(n):
            idx = min(len(scenes) - 1, round(i * len(scenes) / n))
            scene_seq.append(scenes[idx])
    else:
        scene_seq = [None] * n

    shots: List[StoryboardShot] = []
    mid_transition_done = False  # 同场景中段最多插一次情绪拐点转场
    prev_scene_obj: Optional[es.Scene] = None
    prev_emotion = "平静"
    for i in range(n):
        speech = item_for(speech_pool, i)
        spoken = speech[0] if speech else None
        speaker = speech[1] if speech else lead
        narrative_item = item_for(narratives, i)
        narrative = narrative_item[0] if narrative_item else ""

        scene = scene_seq[i]
        prev_scene_obj = scene_seq[i - 1] if i > 0 else None
        scene_text = f"{scene.location} {scene.setting}" if scene else conflict
        prev_text = (
            f"{prev_scene_obj.location} {prev_scene_obj.setting}"
            if prev_scene_obj else ""
        )
        # 情绪：只取本镜台词/叙事片段判断（避免"山门惊变"这类集名
        # 或冲突整句里的情绪词污染整集）；本镜无可判断文本时才兜底
        emotion_src = " ".join(filter(None, [spoken, narrative]))
        if not emotion_src:
            emotion_src = " ".join(filter(None, [conflict, scene_text]))
        if en:
            emotion = _detect_emotion_en(emotion_src)
            if emotion == "Calm":
                emotion = _progress_emotion_en((i + 1) / n, hook_type)
        else:
            emotion = _detect_emotion(emotion_src)
            if emotion == "平静":
                emotion = _progress_emotion((i + 1) / n, hook_type)

        # 转场：首镜开篇 / 换场景 / 情绪拐点（仅一次）/ 集末钩子
        transition = ""
        scene_changed = bool(
            scene and prev_scene_obj and (scene.location != prev_scene_obj.location)
        )
        if i == 0:
            trans_lib = TRANSITION_LIBRARY_EN if en else TRANSITION_LIBRARY
            trans_pick = _pick_transition_for_scene_en if en else _pick_transition_for_scene
            trans_mid = _pick_mid_transition_en if en else _pick_mid_transition
            trans_hook = _pick_hook_transition_en if en else _pick_hook_transition
            transition = trans_lib["Opening" if en else "开篇式"][0]
        elif scene_changed:
            transition = ( _pick_transition_for_scene_en if en
                           else _pick_transition_for_scene )(
                " ".join(filter(None, [scene_text, narrative, conflict, hook]))
            )
        elif (
            not scene_changed and not mid_transition_done
            and i >= 2
        ):
            mid = ( _pick_mid_transition_en if en else _pick_mid_transition )(
                " ".join(filter(None, [narrative, conflict, scene_text])),
                prev_emotion, emotion,
            )
            if mid:
                transition = mid
                mid_transition_done = True
        if i == n - 1 and not transition:
            transition = ( _pick_hook_transition_en if en
                           else _pick_hook_transition )(hook_type)

        # 景别/运镜：冲突与情绪拐点镜用近景/特写，转场镜用远景（M0 规则 7）
        # 只按本镜叙事文本判断，避免 scene_text 整段出现的动作词/场面词
        # 污染全集（与情绪判断同一套本镜优先、无文本才兜底策略）
        text_for_shot = emotion_src
        if en:
            shot_size = _pick_size_en(emotion, text_for_shot)
            camera, camera_note = _pick_camera_en(emotion, text_for_shot)
        else:
            shot_size = _pick_size(emotion, text_for_shot)
            camera, camera_note = _pick_camera(emotion, text_for_shot)
        if transition:
            shot_size = "Wide" if en else "远景"

        if en:
            expression, tone = es.EMOTION_DICT_EN.get(
                emotion, es.EMOTION_DICT_EN["Calm"])
        else:
            expression, tone = es.EMOTION_DICT.get(emotion, es.EMOTION_DICT["平静"])

        actor_text = f"{speaker}" if speaker != narrator_name else (
            "Narrator's view" if en else "旁白视角")
        if spoken:
            if en:
                visual = (
                    f"{actor_text} says \"{spoken}\", presented with "
                    f"{camera_note} at {scene.location if scene else 'the set scene'}"
                )
            else:
                visual = (
                    f"{actor_text}说出\"{spoken}\"，"
                    f"镜头以{camera_note}呈现，位置：{scene.location if scene else '既定场景'}"
                )
        elif emotion != ("Calm" if en else "平静"):
            if en:
                visual = (
                    f"{actor_text} {narrative or 'advances the plot'}, with "
                    f"{emotion} emotion, presented with {camera_note}"
                )
            else:
                visual = (
                    f"{actor_text}{narrative or '推进剧情'}，"
                    f"情绪{emotion}，以{camera_note}呈现"
                )
        else:
            if en:
                visual = (
                    f"{actor_text}: {narrative or scene_text or 'advances the plot'}, "
                    f"presented with {camera_note}"
                )
            else:
                visual = (
                    f"{actor_text}：{narrative or scene_text or '推进剧情'}，"
                    f"镜头以{camera_note}呈现"
                )
        if en:
            dialogue = (
                f"[{speaker}] \"{spoken}\"" if spoken and speaker != narrator_name
                else (f"[Narrator] \"{spoken}\"" if spoken else "")
            )
        else:
            dialogue = (
                f"【{speaker}】\"{spoken}\"" if spoken and speaker != "旁白"
                else (f"【旁白】\"{spoken}\"" if spoken else "")
            )

        shots.append(
            StoryboardShot(
                shot=i + 1,
                shot_size=shot_size,
                camera=camera,
                visual=(_clip_en(visual) if en else _clip(visual)),
                dialogue=dialogue if dialogue else None,
                character=speaker,
                emotion=emotion,
                expression=expression,
                tone=tone,
                duration=durations[i],
                camera_note=camera_note,
                transition=transition,
            )
        )
        prev_emotion = emotion
    return shots


# ------------------- 全计划拆解 -------------------


def enrich_storyboard(plan: es.EpisodePlan) -> es.EpisodePlan:
    """对 T07/T08 EpisodePlan 逐集生成分镜表（就地替换 shots，保留原结构）。"""
    for ep in plan.episodes:
        ep.shots = storyboard_episode(ep)  # type: ignore[assignment]
    return plan


def build_storyboard_plan(
    raw_text: str,
    template: Optional[str] = None,
    target_duration: int = es.DEFAULT_TARGET_DURATION,
    shots_per_minute: int = es.SHOTS_PER_MINUTE,
) -> es.EpisodePlan:
    """完整链路：T06 解析 -> T07 拆集 -> T08 角色关系 -> T11-T15 分镜拆解。"""
    import character_relations as cr

    plan = cr.build_enriched_plan(
        raw_text, template=template,
        target_duration=target_duration, shots_per_minute=shots_per_minute,
    )
    return enrich_storyboard(plan)


# ------------------- 渲染 -------------------


def _dialog_plain(dialogue: Optional[str]) -> str:
    """把「【角色】"内容"」转为「角色："内容"」，去掉多余括号符号。"""
    if not dialogue:
        return ""
    s = dialogue.strip()
    m = re.match(r"^【([^】]+)】\s*([\u201c\"].*?[\u201d\"])$", s)
    if m:
        return f"{m.group(1)}：{m.group(2)}"
    return s


def render_storyboard_text(
    plan: es.EpisodePlan, break_by_shot: bool = False
) -> str:
    """输出纯文本分镜稿（.txt，减少不必要的标点符号）。

    这是「可直接粘贴 AI 动漫工具」的文字档格式：
    - 不使用 Markdown 表格竖线 / 圆点分隔线等装饰符号；
    - 每镜一行核心信息，台词转成「角色：内容」而不是【角色】加引号包裹；
    - break_by_shot=True（输入超过 800 字）时按「分镜节点」分段落：
      每个分镜块之间空行分隔，便于阅读与逐镜粘贴；≤800 字时紧凑连排；
    - 台词为空时省略台词行，转场为空时省略转场行；
    - 首行为输入类型说明，命中红线时保留警示行。
    """
    en = getattr(plan, "language", "zh") == "en"
    out: List[str] = []
    if en:
        out.append(f"Storyboard script (input type: {plan.input_type_label})")
    else:
        out.append(f"剧本分镜稿（输入类型：{plan.input_type_label}）")
    if plan.sensitive_hits:
        if en:
            out.append("Note: sensitive categories hit "
                       f"{'、'.join(plan.sensitive_hits)}, please review first")
        else:
            out.append(f"注意：命中红线类别 {'、'.join(plan.sensitive_hits)}，请人工确认后继续")

    for ep in plan.episodes:
        out.append("")
        if en:
            out.append(f"Episode {ep.episode}｜Target {ep.target_duration} seconds")
            out.append(f"Core conflict: {ep.core_conflict}")
            out.append(f"Episode hook: {ep.episode_hook}")
        else:
            out.append(f"第 {ep.episode} 集｜目标时长 {ep.target_duration} 秒")
            out.append(f"核心冲突：{ep.core_conflict}")
            out.append(f"集末钩子：{ep.episode_hook}")
        shots: List[StoryboardShot] = ep.shots  # type: ignore[assignment]
        for s in shots:
            if en:
                block = [f"Shot{s.shot}｜{s.shot_size}·{s.camera_note} ({s.duration}s)"]
                block.append(f"Visual: {s.visual}")
                if s.dialogue:
                    block.append(f"Dialogue: {_dialog_plain_en(s.dialogue)}")
                block.append(f"Emotion: {s.emotion}")
                block.append(f"Expression: {s.expression}")
                block.append(f"Tone: {s.tone}")
                if s.transition:
                    block.append(f"Transition: {s.transition}")
            else:
                block = [f"镜{s.shot}｜{s.shot_size}·{s.camera_note}（{s.duration}秒）"]
                block.append(f"画面：{s.visual}")
                if s.dialogue:
                    block.append(f"台词：{_dialog_plain(s.dialogue)}")
                block.append(f"情绪：{s.emotion}")
                block.append(f"表情：{s.expression}")
                block.append(f"音调：{s.tone}")
                if s.transition:
                    block.append(f"转场：{s.transition}")
            if break_by_shot:
                out.append("")
            out.extend(block)
        out.append("")

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out).strip()


def render_storyboard_markdown(plan: es.EpisodePlan) -> str:
    """输出含运镜术语与转场列的分镜表（Markdown）。"""
    en = getattr(plan, "language", "zh") == "en"
    out: List[str] = []
    if en:
        out.append(f"# Episode Scripts (input type: {plan.input_type_label})")
    else:
        out.append(f"# 分集剧本（输入类型：{plan.input_type_label}）")
    if plan.sensitive_hits:
        if en:
            out.append("> ⚠ Sensitive categories hit: "
                       f"{'、'.join(plan.sensitive_hits)} (please review first)")
        else:
            out.append(f"> ⚠ 命中红线类别：{'、'.join(plan.sensitive_hits)}（请人工确认后继续）")

    for ep in plan.episodes:
        out.append("")
        if en:
            out.append(f"## Episode {ep.episode} (target {ep.target_duration} seconds)")
            out.append(f"- Core conflict: {ep.core_conflict}")
            out.append(f"- Episode hook ({ep.hook_type}): {ep.episode_hook}")
            out.append("")
            out.append("### Storyboard table")
            out.append(
                "| Shot | Size | Camera | Camera note | Visual | Dialogue/Narration "
                "| Character | Emotion | Expression | Tone | Duration | Transition |"
            )
            out.append(
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            )
        else:
            out.append(f"## 第 {ep.episode} 集（目标时长 {ep.target_duration} 秒）")
            out.append(f"- 核心冲突：{ep.core_conflict}")
            out.append(f"- 集末钩子（{ep.hook_type}）：{ep.episode_hook}")
            out.append("")
            out.append("### 分镜表")
            out.append(
                "| 镜号 | 景别 | 运镜 | 运镜术语 | 画面内容 | 台词/旁白 | "
                "角色 | 情绪 | 表情 | 音调 | 时长 | 转场 |"
            )
            out.append(
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            )
        shots: List[StoryboardShot] = ep.shots  # type: ignore[assignment]
        for s in shots:
            if en:
                dialogue = s.dialogue if s.dialogue else "(none)"
                out.append(
                    f"| {s.shot} | {s.shot_size} | {s.camera} | {s.camera_note} "
                    f"| {s.visual} | {dialogue} | {s.character} | {s.emotion} "
                    f"| {s.expression} | {s.tone} | {s.duration} | {s.transition or '—'} |"
                )
            else:
                dialogue = s.dialogue if s.dialogue else "（无）"
                out.append(
                    f"| {s.shot} | {s.shot_size} | {s.camera} | {s.camera_note} "
                    f"| {s.visual} | {dialogue} | {s.character} | {s.emotion} "
                    f"| {s.expression} | {s.tone} | {s.duration} | {s.transition or '—'} |"
                )
    return "\n".join(out)


def render_storyboard_json(plan: es.EpisodePlan) -> str:
    """输出 JSON（episodes 数组；shot 对象含 camera_note 与 transition）。"""
    return json.dumps(asdict(plan), ensure_ascii=False, indent=2)


# ------------------- 自检：分镜字段完整率 100% + 术语一致 -------------------


def validate_storyboard(plan: es.EpisodePlan) -> List[str]:
    """分镜拆解器自检（对应 T21 质量自检的分镜部分）。

    检查：字段完整性、景别/运镜/情绪枚举、镜头密度、时长合计、
    转场术语合法、转场不乱用（同场景连续镜无转场或为直接切）、
    camera_note 与 camera 大类一致。
    """
    problems: List[str] = []
    if not plan.episodes:
        return ["分镜计划为空"]

    en = getattr(plan, "language", "zh") == "en"
    all_notes: set = set()
    camera_lib = CAMERA_LIBRARY_EN if en else CAMERA_LIBRARY
    trans_lib = TRANSITION_LIBRARY_EN if en else TRANSITION_LIBRARY
    formulas = TRANSITION_FORMULAS_EN if en else TRANSITION_FORMULAS
    sizes = es.SHOT_SIZES_EN if en else es.SHOT_SIZES
    cams = es.CAMERAS_EN if en else es.CAMERAS
    emotions = es.EMOTION_DICT_EN if en else es.EMOTION_DICT
    for fam in camera_lib.values():
        all_notes.update(fam)
    all_transitions: set = set()
    for fam in trans_lib.values():
        all_transitions.update(fam)
    all_transitions.update(formulas)

    for ep in plan.episodes:
        tag = f"Episode {ep.episode}" if en else f"第{ep.episode}集"
        if not ep.shots:
            problems.append(f"{tag}：分镜为空")
            continue
        total = sum(s.duration for s in ep.shots)
        if total != ep.target_duration:
            problems.append(f"{tag}：分镜总时长 {total} != 目标时长")
        shots: List[StoryboardShot] = ep.shots  # type: ignore[assignment]
        for i, s in enumerate(shots):
            if s.shot_size not in sizes:
                problems.append(f"{tag}：景别 {s.shot_size} 不在枚举内")
            if s.camera not in cams:
                problems.append(f"{tag}：运镜 {s.camera} 不在枚举内")
            if not 2 <= s.duration <= 5:
                problems.append(f"{tag}：镜时长 {s.duration} 超 2--5 秒")
            if s.emotion not in emotions:
                problems.append(f"{tag}：情绪 {s.emotion} 不在词典内")
            if s.camera_note not in all_notes:
                problems.append(f"{tag}：运镜术语 {s.camera_note} 不在术语库")
            if s.camera_note not in camera_lib.get(s.camera, []):
                problems.append(
                    f"{tag}：运镜术语 {s.camera_note} 与运镜 {s.camera} 不一致"
                )
            if s.transition and s.transition not in all_transitions:
                problems.append(f"{tag}：转场 {s.transition} 不在转场库")
        actual_per_min = len(ep.shots) / ep.target_duration * 60
        if not 18 <= actual_per_min <= 22:
            problems.append(
                f"{tag}：分镜密度 {actual_per_min:.1f} 镜/分钟超出 18--22"
            )
    return problems


if __name__ == "__main__":
    import sys

    demo = (
        "少年林风来到临安城悦来客栈，遇见仇家赵屠夫。"
        "林风忍气吞声，却被逼到墙角。"
        "林风为救店家女拔剑出手，暴露身份引来更多追兵。"
    )
    p = build_storyboard_plan(demo)
    print(render_storyboard_markdown(p))
    problems = validate_storyboard(p)
    print("\n自检问题:", problems if problems else "无", file=sys.stderr)