# -*- coding: utf-8 -*-
"""T07 分集逻辑单元测试。

运行方式（在 text2script/ 目录下）：
    python -m unittest -v test_episode_splitter
"""

import unittest

import input_parser as ip
import episode_splitter as es


# 四类输入素材（对齐 T05 输入类型）

ONE_LINE = "外卖小哥意外获得读心术，从此逆袭人生"

SUMMARY = (
    "少年王尘修为尽废被逐出宗门，流落凡尘后娶了落魄商贾之女苏婉。"
    "成亲当日遭仇家上门羞辱，王尘忍辱负重，暗中重铸根基。"
    "三个月后宗门大比开启，王尘携妻子重返山门，一鸣惊人。"
)

OUTLINE = (
    "第一卷 初入江湖\n"
    "第一章 客栈风波\n"
    "少年林风来到临安城悦来客栈，遇见仇家赵屠夫。"
    "林风忍气吞声，却被逼到墙角。\n"
    "第二章 拔剑\n"
    "林风为救店家女拔剑出手，暴露身份引来更多追兵。"
)

EXCERPT = (
    "李强推开门，急切说道：“老张，出大事了！”\n"
    "老张放下茶杯，皱眉问道：“什么事这么慌张？”\n"
    "李强压低声音说：“顾沉回来了，而且带着我们当年埋下的证据。”\n"
    "老张脸色骤变：“他怎么会知道？这么多年都过去了。”\n"
    "窗外忽然闪过一道黑影，两人同时噤声。"
) * 20  # 约 2240 字，超过 2000 字分段阈值，触发多块拆集

DEFAULT = 75


class TestSplitEpisodes(unittest.TestCase):
    """主流程与集序衔接。"""

    def test_one_line_produces_one_episode(self):
        plan = es.split_episodes_from_text(ONE_LINE)
        self.assertEqual(plan.input_type, ip.TYPE_ONE_LINE)
        self.assertTrue(plan.needs_expansion)
        self.assertGreaterEqual(len(plan.episodes), 1)

    def test_summary_episodes(self):
        plan = es.split_episodes_from_text(SUMMARY)
        self.assertEqual(plan.input_type, ip.TYPE_SUMMARY)
        self.assertGreaterEqual(len(plan.episodes), 1)

    def test_outline_episodes(self):
        plan = es.split_episodes_from_text(OUTLINE)
        self.assertEqual(plan.input_type, ip.TYPE_OUTLINE)
        self.assertGreaterEqual(len(plan.episodes), 2)

    def test_outline_volume_title_not_separate_episode(self):
        # 大纲开头的纯卷标题不应独立成集
        plan = es.split_episodes_from_text(OUTLINE)
        for ep in plan.episodes:
            self.assertNotIn("第一卷", ep.core_conflict)
            self.assertNotEqual(ep.core_conflict[:5], "第一卷")
        self.assertFalse(
            any("第一卷" == e.core_conflict.strip() for e in plan.episodes)
        )

    def test_excerpt_episodes(self):
        plan = es.split_episodes_from_text(EXCERPT)
        self.assertEqual(plan.input_type, ip.TYPE_EXCERPT)
        self.assertGreaterEqual(len(plan.episodes), 2)

    def test_episode_numbers_sequential(self):
        plan = es.split_episodes_from_text(EXCERPT)
        for idx, ep in enumerate(plan.episodes, start=1):
            self.assertEqual(ep.episode, idx)

    def test_continuity_generated(self):
        plan = es.split_episodes_from_text(OUTLINE)
        self.assertEqual(plan.episodes[0].continuity, "")
        for ep in plan.episodes[1:]:
            self.assertIn("承接第", ep.continuity)
            self.assertIn("集：", ep.continuity)

    def test_empty_text_raises(self):
        with self.assertRaises((ValueError, Exception)):
            es.split_episodes_from_text("   ")

    def test_accepts_parse_result(self):
        parsed = ip.parse_input(OUTLINE)
        plan = es.split_episodes(parsed)
        self.assertGreaterEqual(len(plan.episodes), 2)


class TestEpisodeFields(unittest.TestCase):
    """单集字段：时长、冲突、钩子、场景、角色、台词。"""

    def setUp(self):
        self.plan = es.split_episodes_from_text(SUMMARY)
        self.ep = self.plan.episodes[0]

    def test_target_duration_range(self):
        self.assertTrue(60 <= self.ep.target_duration <= 90)

    def test_core_conflict_present(self):
        self.assertGreaterEqual(len(self.ep.core_conflict),
                                es.CONFLICT_MIN_LENGTH)

    def test_episode_hook_present(self):
        self.assertGreaterEqual(len(self.ep.episode_hook),
                                es.HOOK_MIN_LENGTH)
        self.assertIn(self.ep.hook_type, es.HOOK_TYPES)

    def test_hook_not_flat(self):
        # 集末钩子不应是平淡陈述：长度与类型均满足要求即视为有效
        self.assertTrue(self.ep.episode_hook)
        self.assertIn(self.ep.hook_type, ["悬念", "反转", "危机", "新信息"])

    def test_scenes_at_least_one(self):
        self.assertGreaterEqual(len(self.ep.scenes), 1)
        for sc in self.ep.scenes:
            self.assertIn(sc.time, es.SCENE_TIMES)
            self.assertTrue(sc.location)

    def test_characters_with_roles(self):
        self.assertGreaterEqual(len(self.ep.characters), 1)
        for ch in self.ep.characters:
            self.assertIn(ch.role, es.CHARACTER_ROLES)

    def test_lines_present_and_short(self):
        self.assertGreaterEqual(len(self.ep.lines), 1)
        for ln in self.ep.lines:
            self.assertLessEqual(len(ln.text), es.LINE_MAX_LENGTH)

    def test_named_dialogue_attributed_to_speaker(self):
        raw = ("王尘说：“苏婉，别怕，一切有我。”\n"
               "苏婉问道：“可是仇家已经找上门了，我们该怎么办？”\n"
               "王尘低语：“先把证据藏好，今夜就走。”")
        plan = es.split_episodes_from_text(raw)
        ep = plan.episodes[0]
        speakers = [ln.speaker for ln in ep.lines]
        self.assertIn("王尘", speakers)
        self.assertIn("苏婉", speakers)
        self.assertNotIn("苏婉问", speakers)
        self.assertNotIn("旁白", speakers)

    def test_narration_not_split_by_measure_word_dao(self):
        # 「一道黑影」的「道」是量词，不应被拆成角色名
        raw = "王尘说：“苏婉，别怕。”窗外忽然闪过一道黑影，王尘脸色骤变。"
        plan = es.split_episodes_from_text(raw)
        names = [c.name for ep in plan.episodes for c in ep.characters]
        self.assertFalse(any("闪过" in n or n.endswith("道") for n in names),
                         f"出现误拆角色名: {names}")

    def test_questioner_not_marked_villain(self):
        # 叙述句中「提到仇家」的提问者不应被标为反派
        raw = ("苏婉问道：“可是仇家已经找上门了，我们该怎么办？”\n"
               "王尘说：“先把证据藏好，今夜就走。”")
        plan = es.split_episodes_from_text(raw)
        ep = plan.episodes[0]
        suwan = next(c for c in ep.characters if c.name == "苏婉")
        self.assertNotEqual(suwan.role, "反派")

    def test_line_clip(self):
        long_line = "这句话非常非常非常非常非常非常非常非常非常非常非常非常非常长超出限制"
        clipped = es.clip_line(long_line)
        self.assertLessEqual(len(clipped), es.LINE_MAX_LENGTH)


class TestShots(unittest.TestCase):
    """分镜草稿：景别/运镜枚举、时长、密度、台词。"""

    def setUp(self):
        self.plan = es.split_episodes_from_text(EXCERPT)
        self.ep = self.plan.episodes[0]

    def test_shot_enums(self):
        for s in self.ep.shots:
            self.assertIn(s.shot_size, es.SHOT_SIZES)
            self.assertIn(s.camera, es.CAMERAS)

    def test_shot_duration_range_and_sum(self):
        total = sum(s.duration for s in self.ep.shots)
        self.assertEqual(total, self.ep.target_duration)
        for s in self.ep.shots:
            self.assertTrue(es.SHOT_MIN_DURATION <= s.duration
                            <= es.SHOT_MAX_DURATION)

    def test_shot_density(self):
        per_min = len(self.ep.shots) / self.ep.target_duration * 60
        self.assertTrue(18 <= per_min <= 22)

    def test_shot_shot_number_sequential(self):
        for i, s in enumerate(self.ep.shots, start=1):
            self.assertEqual(s.shot, i)

    def test_shot_emotion_in_dict(self):
        for s in self.ep.shots:
            self.assertIn(s.emotion, es.EMOTION_DICT)


class TestValidatePlan(unittest.TestCase):
    """validate_plan 自检通过；构造违规样本时能发现问题。"""

    def test_valid_plan_no_problems(self):
        for raw in (ONE_LINE, SUMMARY, OUTLINE, EXCERPT):
            plan = es.split_episodes_from_text(raw)
            self.assertEqual(es.validate_plan(plan), [], raw[:10])

    def test_detect_bad_duration(self):
        plan = es.split_episodes_from_text(SUMMARY)
        plan.episodes[0].target_duration = 30
        problems = es.validate_plan(plan)
        self.assertTrue(any("目标时长" in p for p in problems))

    def test_detect_long_line(self):
        plan = es.split_episodes_from_text(SUMMARY)
        plan.episodes[0].lines[0].text = "超" * (es.LINE_MAX_LENGTH + 1)
        problems = es.validate_plan(plan)
        self.assertTrue(any("台词超" in p for p in problems))

    def test_detect_bad_shot_enum(self):
        plan = es.split_episodes_from_text(SUMMARY)
        plan.episodes[0].shots[0].shot_size = "大远景"
        problems = es.validate_plan(plan)
        self.assertTrue(any("景别" in p for p in problems))


class TestSensitiveHits(unittest.TestCase):
    """红线信息从 T06 透传至计划。"""

    def test_hits_passed_through(self):
        raw = "故事里出现虐杀镜头，还夹杂着算命改运的情节。"
        plan = es.split_episodes_from_text(raw)
        self.assertIn("血腥暴力", plan.sensitive_hits)
        self.assertIn("封建迷信", plan.sensitive_hits)


class TestDialogueAttribution(unittest.TestCase):
    """T23 修复 F2：冒号前置与引号后置说话人的台词归属。"""

    def test_colon_structure_attributed(self):
        # 「XX动作：(台词)」冒号结构：台词应归属角色而非旁白
        raw = "阿凯咧嘴一笑：「怕什么，都是节目效果。」他转身朝二楼走。"
        plan = es.split_episodes_from_text(raw)
        ep = plan.episodes[0]
        speakers = [ln.speaker for ln in ep.lines]
        self.assertIn("阿凯", speakers)
        self.assertNotIn("旁白", speakers)

    def test_postposed_speaker_attributed(self):
        # 「(台词)」XX动作…：引号后置说话人应被识别
        raw = "「兄弟们看见没，这就是传说中的凶宅。」阿凯压低声音，把镜头扫向楼梯口。"
        plan = es.split_episodes_from_text(raw)
        ep = plan.episodes[0]
        speakers = [ln.speaker for ln in ep.lines]
        self.assertIn("阿凯", speakers)

    def test_corner_quote_full_pipeline(self):
        # F1+F2 集成：直角引号 + 后置/冒号说话人整链路不丢失台词
        raw = (
            "深夜，探灵主播阿凯走进凶宅开始直播。\n"
            "「兄弟们看见没，就是这栋凶宅。」阿凯压低声音。\n"
            "画面里传来阿凯颤抖的声音：「我、我动不了……」"
        )
        plan = es.split_episodes_from_text(raw)
        self.assertEqual(plan.input_type, ip.TYPE_EXCERPT)
        ep = plan.episodes[0]
        speakers = [ln.speaker for ln in ep.lines]
        self.assertGreaterEqual(sum(1 for s in speakers if s == "阿凯"), 2)
        all_text = "".join(ln.text for ln in ep.lines)
        self.assertIn("我、我动不了", all_text)

    def test_ambiguous_quote_falls_to_narration(self):
        # 引号前后无已知角色名时仍归旁白，不做强行归属
        raw = "“你走吧。”她说完，转身离开了车站。"
        plan = es.split_episodes_from_text(raw)
        speakers = [ln.speaker for ln in plan.episodes[0].lines]
        self.assertIn("旁白", speakers)

    def test_phrase_characters_extracted(self):
        # 冒号/后置短语中的角色名进入角色表，不再只剩占位「主角」
        text = "阿凯咧嘴一笑：“怕什么。”沈铭脸色煞白：“你怎么知道？”"
        names = [c.name for c in es._extract_characters(text)]
        self.assertIn("阿凯", names)
        self.assertIn("沈铭", names)

    def test_pronoun_phrase_not_name(self):
        # 代词开头的短语不误当角色名（如「他笑了笑」）
        text = "他笑了笑，“我有船票。”"
        names = [c.name for c in es._extract_characters(text)]
        self.assertTrue(all(not n.startswith("他") for n in names))

    def test_group_word_not_name(self):
        # 引号后置的群体词不误当说话人（如「。满堂宾客的目光」）
        text = "“抱歉啊。”满堂宾客的目光齐刷刷看过来。"
        names = [c.name for c in es._extract_characters(text)]
        self.assertNotIn("满堂", names)


class TestRendering(unittest.TestCase):
    """Markdown / JSON 渲染。"""

    def setUp(self):
        self.plan = es.split_episodes_from_text(OUTLINE)

    def test_markdown_contains_episodes(self):
        md = es.render_markdown(self.plan)
        self.assertIn("## 第 1 集", md)
        self.assertIn("## 第 2 集", md)
        self.assertIn("核心冲突", md)
        self.assertIn("集末钩子", md)
        self.assertIn("分镜草稿", md)

    def test_markdown_no_shots_when_off(self):
        md = es.render_markdown(self.plan, with_shots=False)
        self.assertNotIn("分镜草稿", md)

    def test_json_roundtrip(self):
        import json as _json
        data = _json.loads(es.render_json(self.plan))
        self.assertEqual(len(data["episodes"]), len(self.plan.episodes))
        self.assertIn("input_type", data)
        self.assertTrue(data["episodes"][0]["episode_hook"])


EN_TEXT = (
    "A delivery rider named Jack gets a strange power: he can read minds. "
    'One day, an old woman asks him for help: "Please find my grandson!" '
    "Her grandson has been kidnapped by gangsters. "
    "Jack hesitates at first, but he remembers his promise to protect the weak. "
    "He follows the gangsters to a warehouse and confronts them alone. "
    "At the end, Jack saves the boy, but the gang leader swears revenge."
)


class TestEnglishMode(unittest.TestCase):
    """英文输入 -> 英文拆分与渲染（v1.2.0 语言匹配核心）。"""

    def setUp(self):
        self.plan = es.split_episodes_from_text(EN_TEXT)

    def test_plan_language_is_en(self):
        self.assertEqual(self.plan.language, "en")

    def test_episode_language_is_en(self):
        self.assertTrue(self.plan.episodes)
        for ep in self.plan.episodes:
            self.assertEqual(ep.language, "en")

    def test_characters_in_english_enum(self):
        for ep in self.plan.episodes:
            for c in ep.characters:
                self.assertIn(c.role, es.CHARACTER_ROLES_EN)

    def test_shots_english_enums(self):
        shots = self.plan.episodes[0].shots
        self.assertTrue(shots)
        for s in shots:
            self.assertIn(s.shot_size, es.SHOT_SIZES_EN)
            self.assertIn(s.camera, es.CAMERAS_EN)

    def test_conflict_and_hook_english(self):
        ep = self.plan.episodes[0]
        self.assertTrue(ep.core_conflict.isascii())
        self.assertTrue(ep.episode_hook.isascii())

    def test_markdown_english_frames(self):
        md = es.render_markdown(self.plan)
        self.assertIn("## Episode 1", md)
        self.assertIn("Core conflict", md)
        self.assertIn("Episode hook", md)
        self.assertNotIn("第 1 集", md)

    def test_lines_narrator_or_names(self):
        ep = self.plan.episodes[0]
        self.assertTrue(ep.lines)
        valid = {"Narrator"} | {c.name for c in ep.characters}
        for ln in ep.lines:
            self.assertIn(ln.speaker, valid)
            self.assertTrue(ln.text.isascii())


if __name__ == "__main__":
    unittest.main()