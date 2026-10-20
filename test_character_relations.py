# -*- coding: utf-8 -*-
"""T08 角色与关系线提取单元测试。

运行方式（在 text2script/ 目录下）：
    python -m unittest -v test_character_relations
"""

import unittest

import episode_splitter as es
import character_relations as cr
from character_relations import (
    CharacterRelation,
    _candidate_ok,
    _speaker_for_phrase,
    assign_line_speakers,
    discover_narration_names,
    extract_relations,
    summarize_relations,
    enrich_episode,
    build_enriched_plan,
    appearance_timeline,
)


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
) * 20  # 约 2240 字，触发分段拆集


def _line(speaker: str, text: str) -> es.Line:
    return es.Line(speaker=speaker, tone="平稳", text=text)


class TestCandidateOk(unittest.TestCase):
    """候选名合法性过滤。"""

    def test_normal_name(self):
        self.assertTrue(_candidate_ok("王尘"))
        self.assertTrue(_candidate_ok("林风"))
        self.assertTrue(_candidate_ok("苏婉"))

    def test_blacklist_rejected(self):
        for name in ("声音", "商人", "众人", "两人", "双方", "心中"):
            self.assertFalse(_candidate_ok(name), name)


class TestSpeakerForPhrase(unittest.TestCase):
    """说话人综合定位：隔词归属 / 对宾保守 / 动作动词挖掘。"""

    def test_gap_action_verb(self):
        # 「林风握紧剑柄，沉声道」：名字与说话动词之间隔着动作
        self.assertEqual(
            _speaker_for_phrase("林风握紧剑柄，沉声道", ["林风", "赵屠夫"]), "林风"
        )

    def test_two_names_take_first(self):
        # 「赵屠夫盯着林风，沉声道」：两个已知角色，取最靠前的。
        # 注意宾语「林风」紧跟在「盯着」后，不应被误取为说话人。
        self.assertEqual(
            _speaker_for_phrase("赵屠夫盯着林风，沉声道", ["赵屠夫", "林风"]),
            "赵屠夫",
        )

    def test_object_verb_conservative(self):
        # 唯一已知角色紧跟在「盯着」等对宾动词后 → 是动作对象而非说话人
        self.assertIsNone(
            _speaker_for_phrase("敌方首领盯着林风，沉声道", ["林风"])
        )

    def test_extended_speech_verb(self):
        # 扩展动词表（怒喝）也能定位
        self.assertEqual(_speaker_for_phrase("王尘怒喝", ["王尘"]), "王尘")

    def test_action_verb_discover(self):
        # 无已知角色时由动作动词挖掘主语（「李强推开门」→ 李强）
        self.assertEqual(
            _speaker_for_phrase("李强推开门，急切说道", []), "李强"
        )


class TestAssignLineSpeakers(unittest.TestCase):
    """台词归属增强：把 T07 旁白行归属到隔词说话人。"""

    def test_gap_speaker_assigned(self):
        text = "李强推开门，急切说道：“老张，出大事了！”"
        lines = [_line("旁白", "老张，出大事了！")]
        new_lines = assign_line_speakers(text, lines, ["李强", "老张"])
        self.assertEqual(new_lines[0].speaker, "李强")
        self.assertEqual(new_lines[0].text, "老张，出大事了！")

    def test_two_names_first_wins(self):
        text = "赵屠夫盯着林风，沉声道：“交出账本！”"
        lines = [_line("旁白", "交出账本！")]
        new_lines = assign_line_speakers(
            text, lines, ["赵屠夫", "林风"]
        )
        self.assertEqual(new_lines[0].speaker, "赵屠夫")

    def test_object_verb_keeps_narration(self):
        # 唯一已知角色是动作宾语 → 保守不归属，保持旁白
        text = "敌方首领盯着林风，沉声道：“交出账本！”"
        lines = [_line("旁白", "交出账本！")]
        new_lines = assign_line_speakers(text, lines, ["林风"])
        self.assertEqual(new_lines[0].speaker, "旁白")

    def test_original_list_not_mutated(self):
        text = "李强推开门，急切说道：“老张，出大事了！”"
        lines = [_line("旁白", "老张，出大事了！")]
        assign_line_speakers(text, lines, ["李强"])
        self.assertEqual(lines[0].speaker, "旁白")


class TestDiscoverNarrationNames(unittest.TestCase):
    """纯叙述角色挖掘（前缀/关系/句首主语）。"""

    def test_summary_discovers_protagonist(self):
        names = discover_narration_names(SUMMARY)
        self.assertIn("王尘", names)
        self.assertIn("苏婉", names)

    def test_prefixed_name_with_verb_tail(self):
        # 「少年王尘修为尽废」不能被尾巴「修为」污染成「王尘修」
        names = discover_narration_names("少年王尘修为尽废被逐出宗门。")
        self.assertIn("王尘", names)
        self.assertTrue(all(n != "王尘修" for n in names))

    def test_ally_structure(self):
        names = discover_narration_names("林风与苏婉联手杀出重围。")
        self.assertIn("林风", names)
        self.assertIn("苏婉", names)

    def test_sentence_head_subject(self):
        names = discover_narration_names("林风为救店家女拔剑出手。")
        self.assertIn("林风", names)

    def test_dense_narration_all_three(self):
        # 定语/状语/被动/后置联合密集叙述：林风、赵屠夫、苏婉都应挖出，
        # 且不得把「老者收林风为徒」的动词「收」吞入角色名
        text = ("少年林风为救店家女苏婉，被赵屠夫一掌打落悬崖。"
                "林风醒来后发誓报仇，苏婉不离不弃。"
                "白眉老者收林风为徒，传他剑法。"
                "十年后林风归来，与苏婉联手迎战赵屠夫。")
        names = discover_narration_names(text)
        for expect in ("林风", "苏婉", "赵屠夫"):
            self.assertIn(expect, names, f"缺少 {expect}: {names}")
        self.assertTrue(all(n != "收林风" for n in names), names)

    def test_leading_action_verb_stripped(self):
        # 「老者收林风为徒」→ 只提「林风」，不提「收林风」
        names = discover_narration_names("白眉老者收林风为徒，传他剑法。")
        self.assertIn("林风", names)
        self.assertTrue(all(n != "收林风" for n in names), names)

    def test_passive_and_post_ally(self):
        # 被动「被赵屠夫一掌」与后置联合「归来，与苏婉联手」均可挖掘
        names = discover_narration_names("林风被赵屠夫一掌打倒，苏婉与赵屠夫并肩而立。")
        self.assertIn("赵屠夫", names)
        self.assertIn("苏婉", names)
        self.assertIn("林风", names)

    def test_empty_text(self):
        self.assertEqual(discover_narration_names(""), [])


class TestExtractRelations(unittest.TestCase):
    """关系线提取：对抗/同盟/亲情/主从/爱慕/交易。"""

    def _chars(self, *names):
        return [
            es.Character(
                name=n,
                role="主角" if i == 0 else ("反派" if "赵" in n or "仇" in n else "配角"),
                description="测试",
            )
            for i, n in enumerate(names)
        ]

    def _rels(self, text, *names):
        return extract_relations(text, self._chars(*names))

    def test_conflict(self):
        rels = self._rels("林风与赵屠夫积怨已久，今日必有一战。", "林风", "赵屠夫")
        self.assertTrue(
            any(r.rel_type == "对抗" and r.source == "林风" and r.target == "赵屠夫"
                for r in rels),
            rels,
        )

    def test_alliance_plus_conflict(self):
        # 「联手迎战」同时产出 同盟（林风×苏婉）与 对抗（对赵屠夫），
        # 且不得把赵屠夫误配成同盟
        text = "林风和苏婉联手迎战赵屠夫。"
        rels = self._rels(text, "林风", "苏婉", "赵屠夫")
        types = {(r.source, r.target, r.rel_type) for r in rels}
        self.assertIn(("林风", "苏婉", "同盟"), types)
        self.assertIn(("林风", "赵屠夫", "对抗"), types)
        self.assertNotIn(("林风", "赵屠夫", "同盟"), types)
        self.assertNotIn(("苏婉", "赵屠夫", "同盟"), types)

    def test_compound_sentence_conflict_saved_by_seg(self):
        # 「为救…被…打落」复合句：救→同盟 只给林风×苏婉；
        # 对抗只给含动作片段的赵屠夫 × 其余角色，不得生成林风×苏婉 对抗
        text = "少年林风为救店家女苏婉，被赵屠夫一掌打落悬崖。"
        rels = self._rels(text, "林风", "苏婉", "赵屠夫")
        types = {(r.source, r.target, r.rel_type) for r in rels}
        self.assertIn(("林风", "苏婉", "同盟"), types)
        self.assertIn(("赵屠夫", "林风", "对抗"), types)
        self.assertNotIn(("林风", "赵屠夫", "同盟"), types)
        self.assertNotIn(("苏婉", "赵屠夫", "同盟"), types)
        self.assertNotIn(("林风", "苏婉", "对抗"), types)

    def test_static_conflict_word_no_cross_seg(self):
        # 「A发誓报仇」是静态对抗词，不跨片段把 B 误配成对抗
        text = "林风醒来后发誓报仇，苏婉不离不弃。"
        rels = self._rels(text, "林风", "苏婉")
        types = {(r.source, r.target, r.rel_type) for r in rels}
        self.assertNotIn(("林风", "苏婉", "对抗"), types)

    def test_post_ally_backtracks_left_name(self):
        # 「归来，与苏婉联手迎战」：左名林风被逗号隔开，仍不误配赵屠夫为同盟
        text = "十年后林风归来，与苏婉联手迎战赵屠夫。"
        rels = self._rels(text, "林风", "苏婉", "赵屠夫")
        types = {(r.source, r.target, r.rel_type) for r in rels}
        self.assertIn(("林风", "苏婉", "同盟"), types)
        self.assertIn(("赵屠夫", "林风", "对抗"), types)
        self.assertIn(("苏婉", "赵屠夫", "对抗"), types)
        self.assertNotIn(("苏婉", "赵屠夫", "同盟"), types)

    def test_kinship_wife(self):
        rels = self._rels("苏婉是王尘的妻子。", "苏婉", "王尘")
        self.assertTrue(
            any(r.rel_type == "亲情" and {"苏婉", "王尘"} == {r.source, r.target}
                for r in rels),
            rels,
        )

    def test_master_servant(self):
        rels = self._rels("侍卫阿四誓死效忠林风。", "阿四", "林风")
        self.assertTrue(
            any(r.rel_type == "主从" and r.source == "阿四" and r.target == "林风"
                for r in rels),
            rels,
        )

    def test_kinship_unnamed(self):
        # 单角色 + 称谓 → 与「未命名亲属」的关系
        rels = self._rels("林风的师父已经失踪多年。", "林风")
        self.assertTrue(
            any(r.rel_type == "亲情" and r.source == "林风" and r.target == "师父"
                and "亲属未命名" in r.evidence
                for r in rels),
            rels,
        )

    def test_deal(self):
        rels = self._rels("王尘雇佣赵屠夫护送镖车，代价是十两银子。", "王尘", "赵屠夫")
        self.assertTrue(any(r.rel_type == "交易" for r in rels), rels)

    def test_no_names_returns_empty(self):
        self.assertEqual(extract_relations("天下大乱，群雄逐鹿。", self._chars()), [])


class TestSummarizeRelations(unittest.TestCase):
    def test_summary_text(self):
        rels = [CharacterRelation("林风", "赵屠夫", "对抗", "积怨已久"),
                CharacterRelation("林风", "苏婉", "同盟", "联手")]
        s = summarize_relations(rels)
        self.assertIn("林风×赵屠夫（对抗）", s)
        self.assertIn("林风×苏婉（同盟）", s)

    def test_empty(self):
        self.assertEqual(summarize_relations([]), "")


class TestEnrichEpisode(unittest.TestCase):
    """单集增强：占位清理 / 角色发现 / 关系摘要。"""

    def test_summary_roles_and_relations(self):
        plan = build_enriched_plan(SUMMARY)
        ep = plan.episodes[0]
        names = [c.name for c in ep.characters]
        self.assertEqual(names[0], "王尘")
        self.assertIn("苏婉", names)
        self.assertTrue(ep.relations, ep.relations)
        # validate_plan 不因 relations/新角色而报错
        self.assertEqual(es.validate_plan(plan), [])

    def test_excerpt_chars_no_noise(self):
        plan = build_enriched_plan(EXCERPT)
        for ep in plan.episodes:
            names = {c.name for c in ep.characters}
            self.assertIn("李强", names)
            self.assertIn("老张", names)
            self.assertNotIn("声音", names)
        self.assertEqual(es.validate_plan(plan), [])

    def test_excerpt_placeholder_removed(self):
        # T07 对无标准说话结构的文本会回退占位「主角」，T08 应替换为真实角色
        plan = build_enriched_plan(EXCERPT)
        for ep in plan.episodes:
            names = [c.name for c in ep.characters]
            self.assertNotIn("主角", names)
            self.assertNotIn("配角", names)

    def test_outline_roles(self):
        plan = build_enriched_plan(OUTLINE)
        self.assertEqual(plan.episodes[0].characters[0].name, "林风")
        self.assertGreaterEqual(len(plan.episodes), 2)

    def test_description_has_relation_summary(self):
        plan = build_enriched_plan(SUMMARY)
        ep = plan.episodes[0]
        self.assertTrue(any("×" in c.description for c in ep.characters))

    def test_relations_serializable(self):
        plan = build_enriched_plan(SUMMARY)
        ep = plan.episodes[0]
        self.assertIsInstance(ep.relations, list)
        for rel in ep.relations:
            self.assertIn("source", rel)
            self.assertIn("target", rel)
            self.assertIn("rel_type", rel)
            self.assertIn("evidence", rel)


class TestEnrichPlanIntegration(unittest.TestCase):
    """T06→T07→T08 全链路与红线透传。"""

    def test_sensitive_hits_passthrough(self):
        raw = (
            "少年王尘发现仇家赵屠夫在祠堂里设下血祭。"
            "王尘怒喝：“住手！”赵屠夫冷笑：“你拦得住？”"
        )
        plan = build_enriched_plan(raw)
        self.assertTrue(plan.sensitive_hits, plan.sensitive_hits)

    def test_appearance_timeline(self):
        plan = build_enriched_plan(OUTLINE)
        tl = appearance_timeline(plan)
        self.assertIn("林风", tl)
        self.assertGreaterEqual(len(tl["林风"]), 1)
        for n in ("主角", "配角"):
            self.assertNotIn(n, tl)

    def test_markdown_has_relation_section(self):
        plan = build_enriched_plan(SUMMARY)
        md = es.render_markdown(plan, with_shots=False)
        self.assertIn("### 角色关系", md)

    def test_json_output_contains_relations(self):
        import json
        plan = build_enriched_plan(SUMMARY)
        data = json.loads(es.render_json(plan))
        self.assertIn("relations", data["episodes"][0])
        self.assertGreaterEqual(len(data["episodes"][0]["relations"]), 0)

    def test_emotion_dict_alignment(self):
        # 增强后的分镜情绪仍全部落在词典内（validate_plan 已覆盖，这里显式校验）
        plan = build_enriched_plan(EXCERPT)
        for ep in plan.episodes:
            for s in ep.shots:
                self.assertIn(s.emotion, es.EMOTION_DICT)


if __name__ == "__main__":
    unittest.main()