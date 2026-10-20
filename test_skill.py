# -*- coding: utf-8 -*-
"""阶段 3（T16-T19）Skill 封装与联调测试。

覆盖：
- T16 SKILL.md：frontmatter、触发场景、执行流程、边界说明
- T17 工作流编排：统一入口 text2script.py 单次调用完整产出
- T18 错误处理：无输入/空文本/文件不存在/长文本分段
- T19 示例与 README：3 组示例输入输出 + 使用说明
- CLI 纯净化：stdout 只有 markdown/json，信息行走 stderr
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "text2script.py")
ONE_LINER = "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"


def run_entry(*args, cwd=None):
    """运行统一入口，返回 CompletedProcess。"""
    return subprocess.run(
        [sys.executable, ENTRY, *args],
        capture_output=True, text=True, cwd=cwd or HERE,
        encoding="utf-8",
    )


class TestSkillMd(unittest.TestCase):
    """T16 SKILL.md 存在性与结构。"""

    def test_skill_md_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(HERE, "SKILL.md")))

    def test_skill_md_frontmatter(self):
        with open(os.path.join(HERE, "SKILL.md"), encoding="utf-8") as fh:
            head = fh.read(500)
        self.assertTrue(head.startswith("---"))
        self.assertIn("name: text2script", head)
        self.assertIn("description:", head)

    def test_skill_md_sections(self):
        with open(os.path.join(HERE, "SKILL.md"), encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("触发场景", content)
        self.assertIn("工作流", content)
        self.assertIn("核心约束", content)
        self.assertIn("资源说明", content)
        self.assertIn("边界说明", content)


class TestReadmeAndExamples(unittest.TestCase):
    """T19 示例与 README。"""

    def test_readme_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(HERE, "README.md")))

    def test_example_files_three_groups(self):
        expected = [
            ("input-1-one-line.txt", "output-1-one-line.md"),
            ("input-2-synopsis.txt", "output-2-synopsis.md"),
            ("input-3-outline.txt", "output-3-outline.md"),
        ]
        for fin, fout in expected:
            self.assertTrue(
                os.path.isfile(os.path.join(HERE, "examples", fin)), fin)
            self.assertTrue(
                os.path.isfile(os.path.join(HERE, "examples", fout)), fout)
            with open(os.path.join(HERE, "examples", fout),
                      encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("分镜表", content)

    def test_example_outputs_no_placeholder(self):
        for name in os.listdir(os.path.join(HERE, "examples")):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(HERE, "examples", name),
                      encoding="utf-8") as fh:
                content = fh.read()
            for bad in ("TODO", "TBD", "待补充", "待删"):
                self.assertNotIn(bad, content, f"{name} 含占位符 {bad}")


class TestWorkflow(unittest.TestCase):
    """T17 工作流编排：单次调用完整产出。"""

    def test_text_mode_markdown_stdout_clean(self):
        proc = run_entry("--text", ONE_LINER)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("分集剧本", proc.stdout)
        self.assertIn("分镜表", proc.stdout)
        # stdout 纯净：信息行不在 stdout
        self.assertNotIn("输入类型:", proc.stdout)
        self.assertNotIn("集数:", proc.stdout)
        self.assertNotIn("自检", proc.stdout)
        # 信息行走 stderr
        self.assertIn("输入类型:", proc.stderr)
        self.assertIn("自检", proc.stderr)

    def test_text_mode_json_parseable(self):
        proc = run_entry("--text", ONE_LINER, "--format", "json")
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["input_type"], "one_line")
        self.assertEqual(data["input_type_label"], "一句话创意")
        self.assertTrue(data["needs_expansion"])
        self.assertIsInstance(data["episodes"], list)
        self.assertGreaterEqual(len(data["episodes"]), 1)
        ep = data["episodes"][0]
        for key in ("episode", "core_conflict", "episode_hook", "hook_type",
                    "shots", "scenes", "lines"):
            self.assertIn(key, ep)
        self.assertGreaterEqual(len(ep["shots"]), 1)
        shot = ep["shots"][0]
        for key in ("shot", "shot_size", "camera", "camera_note", "visual",
                    "dialogue", "emotion", "transition"):
            self.assertIn(key, shot)

    def test_file_mode_txt(self):
        path = os.path.join(HERE, "examples", "input-2-synopsis.txt")
        proc = run_entry("--file", path, "--format", "json")
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["input_type"], "summary")

    def test_file_mode_outline_multi_episode(self):
        path = os.path.join(HERE, "examples", "input-3-outline.txt")
        proc = run_entry("--file", path, "--format", "json")
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["input_type"], "outline")
        self.assertGreaterEqual(len(data["episodes"]), 2)

    def test_output_file_write_stdout_empty(self):
        out_path = os.path.join(HERE, ".tmp_skill_out.md")
        try:
            proc = run_entry("--text", ONE_LINER, "--output", out_path)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("分镜表", content)
        finally:
            if os.path.isfile(out_path):
                os.remove(out_path)

    def test_workflow_chain_components_present(self):
        # 工作流编排依赖 T06/T07/T08/T11-T15 模块
        for mod in ("input_parser", "episode_splitter",
                    "character_relations", "storyboard"):
            self.assertTrue(
                os.path.isfile(os.path.join(HERE, f"{mod}.py")), mod)


class TestErrorHandling(unittest.TestCase):
    """T18 错误处理：无输入/空文本/文件不存在/长文本分段。"""

    def test_no_input(self):
        proc = run_entry()
        self.assertNotEqual(proc.returncode, 0)

    def test_empty_text(self):
        proc = run_entry("--text", "   ")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("输入为空", proc.stderr)

    def test_file_not_found(self):
        proc = run_entry("--file", os.path.join(HERE, "no_such_file.txt"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("文件不存在", proc.stderr)

    def test_long_text_chunk_hint(self):
        # 超过 CHUNK_SIZE(2000 字) 触发分段提示
        long_text = "深夜，陈默推开便利店的门，雨滴顺着风衣滑落。" * 120
        self.assertGreater(len(long_text), 2000)
        proc = run_entry("--text", long_text, "--format", "json")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("长文本", proc.stderr)
        self.assertIn("切分", proc.stderr)
        data = json.loads(proc.stdout)
        self.assertGreaterEqual(len(data["episodes"]), 1)


if __name__ == "__main__":
    unittest.main()