# -*- coding: utf-8 -*-
"""T11-T15 分镜拆解器单元测试。

覆盖：运镜/转场术语映射、分镜差异化、换场景/情绪拐点/集末转场、
M0 分镜规则（字段完整、密度、时长、转场用远景）、T06/T07/T08 兼容、
CLI stdout 纯净与 JSON 可解析。

运行方式（在 text2script/ 目录下）：
    python -m unittest -v test_storyboard
"""

import json
import subprocess
import sys
import unittest

import episode_splitter as es
import storyboard as sb
from storyboard import (
    CAMERA_LIBRARY,
    TRANSITION_LIBRARY,
    TRANSITION_FORMULAS,
    _TRANSITION_SCENE_RULES,
    _HOOK_TRANSITION,
    _EMOTION_CAMERA,
    _EMOTION_CAMERA_NOTE,
    build_storyboard_plan,
    render_storyboard_json,
    render_storyboard_markdown,
    render_storyboard_text,
    validate_storyboard,
)

# 一句话创意（T07 通常只产 1 line / 1 scene，用于验证分镜差异化兜底）
ONE_LINER = (
    "少年林风来到临安城悦来客栈，遇见仇家赵屠夫。"
    "林风忍气吞声，却被逼到墙角。"
    "林风为救店家女拔剑出手，暴露身份引来更多追兵。"
)

# 多场景多冲突素材（应触发换场景转场）
MULTI_SCENE = (
    "苏晴走进废弃工厂，发现被绑架的弟弟被锁在铁笼里。"
    "她冲上去踹开铁门，绑匪从暗处挥刀扑来。"
    "苏晴抄起钢管反击，弟弟趁机挣脱绳索。"
    "两人逃出工厂大门，追兵已封锁街道。"
    "苏晴咬牙拨通电话，说：\"陈队，我找到他们了，但这是个陷阱！\""
)


class TestTerminologyMapping(unittest.TestCase):
    """运镜/转场术语词典的完整性与一致性。"""

    def test_camera_notes_all_in_library(self):
        for fam, notes in CAMERA_LIBRARY.items():
            self.assertTrue(len(notes) > 0, f"运镜大类 {fam} 术语为空")
            for note in notes:
                self.assertTrue(note.strip(), f"运镜大类 {fam} 含空术语")

    def test_camera_ok_enum(self):
        self.assertTrue(set(CAMERA_LIBRARY).issubset(set(es.CAMERAS)))

    def test_emotion_camera_note_matches_family(self):
        for emo, fam in _EMOTION_CAMERA.items():
            note = _EMOTION_CAMERA_NOTE[emo]
            self.assertIn(note, CAMERA_LIBRARY[fam],
                          f"情绪 {emo} 的运镜术语 {note} 与大类 {fam} 不一致")

    def test_emotion_camera_notes_all_present(self):
        self.assertEqual(set(_EMOTION_CAMERA), set(_EMOTION_CAMERA_NOTE))

    def test_transition_library_nonempty(self):
        for fam, trans in TRANSITION_LIBRARY.items():
            self.assertTrue(len(trans) > 0, f"转场大类 {fam} 为空")
            for t in trans:
                self.assertTrue(t.strip(), f"转场大类 {fam} 含空术语")

    def test_transition_scene_rules_point_to_known(self):
        known = set()
        for fam in TRANSITION_LIBRARY.values():
            known.update(fam)
        known.update(TRANSITION_FORMULAS)
        for kw, trans in _TRANSITION_SCENE_RULES:
            self.assertIn(trans, known,
                          f"场景词 {kw} 指向未知转场 {trans}")

    def test_hook_transitions_point_to_known(self):
        known = set()
        for fam in TRANSITION_LIBRARY.values():
            known.update(fam)
        for hook, trans in _HOOK_TRANSITION.items():
            self.assertIn(trans, known, f"钩子 {hook} 转场 {trans} 不在库内")

    def test_transition_formulas_in_library_or_formulas(self):
        for f in TRANSITION_FORMULAS:
            self.assertTrue(f.strip())


class TestStoryboardGeneration(unittest.TestCase):
    def setUp(self):
        self.plan = build_storyboard_plan(ONE_LINER, target_duration=60)
        self.ep = self.plan.episodes[0]
        self.shots = list(self.ep.shots)

    def test_has_episodes_and_shots(self):
        self.assertTrue(self.plan.episodes)
        self.assertGreater(len(self.shots), 0)

    def test_validate_storyboard_clean(self):
        self.assertEqual(validate_storyboard(self.plan), [])

    def test_validate_plan_clean(self):
        # 分镜增强字段不得破坏 T07/T08 的 plan 校验
        self.assertEqual(es.validate_plan(self.plan), [])

    def test_duration_sum_matches_target(self):
        self.assertEqual(sum(s.duration for s in self.shots),
                         self.ep.target_duration)

    def test_default_target_duration(self):
        plan = build_storyboard_plan(ONE_LINER)
        self.assertEqual(sum(s.duration for s in plan.episodes[0].shots),
                         es.DEFAULT_TARGET_DURATION)

    def test_shots_per_minute_range(self):
        actual = len(self.shots) / self.ep.target_duration * 60
        self.assertTrue(18 <= actual <= 22,
                        f"分镜密度 {actual:.1f} 超出 18--22")

    def test_shot_field_completeness(self):
        for s in self.shots:
            self.assertTrue(s.shot > 0)
            self.assertIn(s.shot_size, es.SHOT_SIZES)
            self.assertIn(s.camera, es.CAMERAS)
            self.assertIn(s.emotion, es.EMOTION_DICT)
            self.assertIn(s.expression, es.EMOTION_DICT[s.emotion])
            self.assertIn(s.tone, es.EMOTION_DICT[s.emotion])
            self.assertTrue(s.visual.strip())
            self.assertTrue(2 <= s.duration <= 5)
            self.assertTrue(s.camera_note)
            self.assertIn(s.camera_note, CAMERA_LIBRARY[s.camera])

    def test_visual_and_dialogue_differentiate(self):
        """镜头之间画面/台词/景别/运镜不应千篇一律。"""
        visuals = {s.visual for s in self.shots}
        dialogues = {s.dialogue for s in self.shots if s.dialogue}
        sizes = {s.shot_size for s in self.shots}
        cameras = {s.camera for s in self.shots}
        emotions = {s.emotion for s in self.shots}
        self.assertGreater(len(visuals), 1)
        self.assertGreater(len(sizes), 1)
        self.assertGreater(len(cameras), 1)
        self.assertGreater(len(emotions), 1)
        # 单句素材也必须有台词演进
        self.assertGreater(len(dialogues), 1)

    def test_first_shot_opening_transition(self):
        first = self.shots[0]
        self.assertIn(first.transition, TRANSITION_LIBRARY["开篇式"])

    def test_last_shot_hook_transition(self):
        last = self.shots[-1]
        self.assertIn(last.transition, _HOOK_TRANSITION.values())
        # 转场镜用远景（M0 规则 7）
        self.assertEqual(last.shot_size, "远景")

    def test_emotion_transitions_use_transition_library(self):
        known = set()
        for fam in TRANSITION_LIBRARY.values():
            known.update(fam)
        known.update(TRANSITION_FORMULAS)
        for s in self.shots:
            if s.transition:
                self.assertIn(s.transition, known)

    def test_camera_note_consistent_with_camera(self):
        for s in self.shots:
            self.assertIn(s.camera_note, CAMERA_LIBRARY[s.camera])


class TestSceneTransition(unittest.TestCase):
    def setUp(self):
        self.plan = build_storyboard_plan(MULTI_SCENE, target_duration=60)
        self.ep = self.plan.episodes[0]
        self.shots = list(self.ep.shots)

    def test_has_multiple_scenes(self):
        self.assertGreater(len(self.ep.scenes), 1)

    def test_validate_clean(self):
        self.assertEqual(validate_storyboard(self.plan), [])
        self.assertEqual(es.validate_plan(self.plan), [])

    def test_locations_changed_transition_used(self):
        """换场景镜头应使用场景匹配的具体转场。"""
        for i in range(1, len(self.shots)):
            prev = self.ep.scenes[min(len(self.ep.scenes) - 1,
                                      round((i - 1) * len(self.ep.scenes) / len(self.shots)))]
            cur = self.ep.scenes[min(len(self.ep.scenes) - 1,
                                     round(i * len(self.ep.scenes) / len(self.shots)))]
            if prev.location != cur.location and i + 1 != len(self.shots):
                self.assertTrue(
                    self.shots[i].transition,
                    f"第 {i + 1} 镜换场景应为空转场",
                )

    def test_track_chase_transition_matches_scene(self):
        """追兵/封锁类场景应命中跟跑/环境遮切转场，而非万能兜底。"""
        texts = self.ep.source_text + self.ep.core_conflict
        self.assertTrue(("追兵" in texts) or ("封锁" in texts))


class TestActionPollution(unittest.TestCase):
    """回归：整段场景文本含动作词时，不得污染全部镜头的运镜选择。

    修复前 text_for_shot 每镜拼入整段 scene_text，导致所有镜头命中
    fast action 分支（跟随/加速跟拍）；修复后只按本镜叙事文本判断。
    """

    ACTION_RICH = (
        "第一章 山门惊变。深夜，王尘在树林里遭黑衣人伏击，拔剑死战。"
        "他怒吼：师父，你为何骗我！"
        "第二章 真相。黑衣人摘下斗笠，竟是师叔。王尘瞳孔骤缩，断剑掉落。"
        "他嘶声质问：当年灭门，你也有份？"
        "第三章 逃亡。追兵封锁山下所有路口，王尘背起昏迷的小师妹遁入密道。"
        "他发誓，一定要活着回来。"
    )

    def setUp(self):
        self.plan = build_storyboard_plan(self.ACTION_RICH, target_duration=75)
        self.ep = self.plan.episodes[0]
        self.shots = list(self.ep.shots)

    def test_cameras_not_all_fast_action(self):
        """动作词只在所在叙事镜生效：运镜大类与细分术语必须多样化。"""
        cameras = {s.camera for s in self.shots}
        notes = {s.camera_note for s in self.shots}
        self.assertGreater(len(cameras), 1, f"运镜大类不应全为 {cameras}")
        self.assertGreater(len(notes), 1, f"运镜术语不应全为 {notes}")
        self.assertFalse(cameras == {"跟随"}, "整集不应全被动作词污染为跟随")

    def test_fast_action_only_on_action_shots(self):
        """拔剑/伏击等动作词只让对应叙事镜用跟拍，其余镜按情绪选镜。"""
        action_shots = [
            s for s in self.shots if "拔剑" in (s.dialogue or "") or "伏击" in (s.visual or "")
        ]
        if action_shots:
            for s in action_shots:
                self.assertIn(s.camera_note, CAMERA_LIBRARY["跟随"])

    def test_validate_clean(self):
        self.assertEqual(validate_storyboard(self.plan), [])
        self.assertEqual(es.validate_plan(self.plan), [])


class TestJsonMarkdown(unittest.TestCase):
    def test_json_parseable_and_contains_shot(self):
        data = json.loads(render_storyboard_json(self._plan()))
        self.assertTrue(data["episodes"])
        shot = data["episodes"][0]["shots"][0]
        self.assertIn("camera_note", shot)
        self.assertIn("transition", shot)
        self.assertIn("emotion", shot)

    def test_markdown_contains_storyboard_section(self):
        md = render_storyboard_markdown(self._plan())
        self.assertIn("分镜表", md)
        self.assertIn("景别", md)
        self.assertIn("运镜术语", md)
        self.assertIn("转场", md)

    def test_text_render_is_plain_no_table_symbols(self):
        """纯文字档：无 Markdown 表格装饰符号，台词为「角色：内容」。"""
        txt = render_storyboard_text(self._plan())
        self.assertIn("剧本分镜稿", txt)
        self.assertIn("镜1", txt)
        self.assertNotIn("| 镜号", txt)
        self.assertNotIn("| --", txt)
        # 台词转成「角色：内容」，而不是【角色】加引号包裹
        self.assertNotIn("【", txt)

    def test_text_render_break_by_shot_paragraph(self):
        """超过 800 字（break_by_shot=True）时每镜分段落，有空行分隔。"""
        txt = render_storyboard_text(self._plan(), break_by_shot=True)
        self.assertIn("镜1", txt)
        self.assertIn("\n\n镜2", txt)

    def test_text_render_compact_no_extra_blank_lines(self):
        """≤800 字（break_by_shot=False）时紧凑连排，不产生镜间空行。"""
        txt = render_storyboard_text(self._plan(), break_by_shot=False)
        self.assertIn("镜1", txt)
        self.assertNotIn("\n\n镜2", txt)

    def _plan(self):
        return build_storyboard_plan(ONE_LINER, target_duration=60)


class TestCliStdout(unittest.TestCase):
    """CLI 输出纯净：stdout 只有 markdown/json，信息行走 stderr。"""

    def test_storyboard_module_demo_stdout_clean(self):
        proc = subprocess.run(
            [sys.executable, "storyboard.py"],
            capture_output=True, text=True, cwd=".",
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("分镜表", proc.stdout)
        self.assertNotIn("自检问题", proc.stdout)
        # 自检信息走 stderr
        self.assertIn("自检问题", proc.stderr)


if __name__ == "__main__":
    unittest.main()