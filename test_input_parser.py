# -*- coding: utf-8 -*-
"""T06 输入解析器单元测试。

运行方式（在 text2script/ 目录下）：
    python -m unittest -v test_input_parser
"""

import unittest

import input_parser as ip


class TestTypeDetection(unittest.TestCase):
    """四类输入识别。"""

    def test_one_line(self):
        text = "一个外卖骑手意外获得读心术，从此逆袭人生"
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_ONE_LINE)

    def test_one_line_within_60_chars(self):
        text = "赘婿崛起"
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_ONE_LINE)

    def test_one_line_requires_no_newline(self):
        # 超过 60 字但仍是单行，应归为梗概/片段类，而不是一句话
        text = "一位隐世高手因为婚约入赘豪门，受尽白眼后展露真正实力，" * 3
        self.assertNotEqual(ip.detect_input_type(text), ip.TYPE_ONE_LINE)

    def test_summary(self):
        text = (
            "少年王尘修为尽废被逐出宗门，流落凡尘后娶了落魄商贾之女苏婉。"
            "成亲当日遭仇家上门羞辱，王尘忍辱负重，暗中重铸根基。"
            "三个月后宗门大比开启，王尘携妻子重返山门，一鸣惊人。"
        )
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_SUMMARY)

    def test_excerpt_by_length(self):
        text = "他缓缓抬起头，目光如炬。" * 100  # > 800 字
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_EXCERPT)

    def test_excerpt_by_dialogue(self):
        text = (
            "李强推开门，急切地说道：“老张，出大事了！”\n"
            "老张放下茶杯，皱眉问道：“什么事这么慌张？”"
        )
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_EXCERPT)

    def test_excerpt_by_corner_quote_dialogue(self):
        # T23 F1：中文网文常用的「」直角引号对话也应识别为小说片段
        text = (
            "阿凯咧嘴一笑：「怕什么，都是节目效果。」\n"
            "沈铭脸色煞白：「你、你怎么知道？」"
        )
        cleaned = ip.clean_text(text)
        self.assertEqual(ip.detect_input_type(cleaned), ip.TYPE_EXCERPT)

    def test_outline(self):
        text = (
            "第一卷 初入江湖\n"
            "第一章 客栈风波\n"
            "少年林风来到临安城，在悦来客栈偶遇仇家。\n"
            "第二章 拔剑\n"
            "林风为救店家女出手，暴露身份。"
        )
        self.assertEqual(ip.detect_input_type(text), ip.TYPE_OUTLINE)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            ip.detect_input_type("   ")

    def test_labels_present(self):
        self.assertEqual(len(ip.INPUT_TYPE_LABELS), 4)


class TestExpansion(unittest.TestCase):
    """扩写判断：仅一句话创意需要扩写。"""

    def test_one_line_needs_expansion(self):
        self.assertTrue(ip.needs_expansion(ip.TYPE_ONE_LINE))

    def test_others_no_expansion(self):
        self.assertFalse(ip.needs_expansion(ip.TYPE_SUMMARY))
        self.assertFalse(ip.needs_expansion(ip.TYPE_EXCERPT))
        self.assertFalse(ip.needs_expansion(ip.TYPE_OUTLINE))


class TestCleaning(unittest.TestCase):
    """文本清洗：目录/噪音行/空行/全角空格/标点。"""

    def test_remove_common_noise(self):
        raw = (
            "封面\n"
            "版权页\n"
            "目录\n"
            "第一章 前夜\n"
            "正文内容第一行。\n"
            "天才一秒记住本站地址\n"
            "页脚\n"
            "3\n"
        )
        cleaned = ip.clean_text(raw)
        self.assertNotIn("封面", cleaned)
        self.assertNotIn("版权页", cleaned)
        self.assertNotIn("目录", cleaned)
        self.assertNotIn("天才一秒记住", cleaned)
        self.assertNotIn("页脚", cleaned)
        self.assertIn("第一章", cleaned)
        self.assertIn("正文内容第一行", cleaned)

    def test_toc_region_removed(self):
        raw = (
            "目录\n"
            "第一章 前夜 1\n"
            "第二章 拔剑 12\n"
            "第三章 归途 30\n"
            "第一章 前夜\n"
            "夜晚的风掠过窗棂。"
        )
        cleaned = ip.clean_text(raw)
        self.assertNotIn("第一章 前夜 1", cleaned)
        self.assertIn("夜晚的风掠过窗棂", cleaned)

    def test_fullwidth_space_removed(self):
        text = "他\u3000站在\u3000门前。"
        self.assertNotIn("\u3000", ip.clean_text(text))

    def test_collapse_blank_lines(self):
        raw = "第一段。\n\n\n\n\n第二段。"
        cleaned = ip.clean_text(raw)
        self.assertNotIn("\n\n\n", cleaned)
        # 折叠后最多保留一个空行作为段落分隔
        self.assertEqual(cleaned.count("\n"), 2)

    def test_punctuation_unified(self):
        text = "你好,今天天气如何?准备出发!"
        cleaned = ip.clean_text(text)
        self.assertIn("，", cleaned)
        self.assertIn("？", cleaned)
        self.assertIn("！", cleaned)
        self.assertNotIn(",", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn("!", cleaned)

    def test_decimal_point_kept(self):
        text = "比例是3.14，成绩为90.5分。"
        cleaned = ip.clean_text(text)
        self.assertIn("3.14", cleaned)
        self.assertIn("90.5", cleaned)

    def test_dialogue_quotes_kept(self):
        text = '他说道："快走!"'
        cleaned = ip.clean_text(text)
        self.assertIn("“", cleaned)
        self.assertIn("”", cleaned)

    def test_corner_quotes_unified(self):
        # T23 F1：直角引号「」统一为中文弯引号，成对转换
        self.assertEqual(ip.unify_punctuation("「你好」"), "“你好”")
        self.assertEqual(ip.unify_punctuation("他说：「快跑！」"),
                         "他说：“快跑！”")
        # 连续两段直角引号对话交替正确
        self.assertEqual(ip.unify_punctuation("「甲」他说。「乙」"),
                         "“甲”他说。“乙”")

    def test_corner_quote_dialogue_detected(self):
        # T23 F1：清洗后「」对话可被对话检测命中
        text = "阿凯咧嘴一笑：「怕什么，都是节目效果。」"
        cleaned = ip.clean_text(text)
        self.assertTrue(ip._has_dialogue(cleaned))
        self.assertNotIn("「", cleaned)

    def test_blank_text(self):
        self.assertEqual(ip.clean_text(""), "")


class TestSplitting(unittest.TestCase):
    """超长分段：章节优先，否则 2000 字切块 + 100 字重叠。"""

    def test_chapter_priority(self):
        text = (
            "第一章 开端\n" + "甲" * 500 + "\n"
            "第二章 发展\n" + "乙" * 300 + "\n"
            "第三章 结局\n" + "丙" * 200
        )
        chunks = ip.split_long_text(text)
        self.assertEqual(len(chunks), 3)
        self.assertIn("第一章 开端", chunks[0])
        self.assertIn("第三章 结局", chunks[2])

    def test_no_chapter_chunking(self):
        text = "心" * 4500
        chunks = ip.split_long_text(text, chunk_size=2000, overlap=100)
        self.assertGreaterEqual(len(chunks), 2)
        # 相邻块存在 100 字重叠
        overlap_text = chunks[0][-100:] if len(chunks[0]) >= 100 else chunks[0]
        self.assertIn(overlap_text, chunks[1])

    def test_short_text_single_chunk(self):
        text = "短短一段。"
        chunks = ip.split_long_text(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_empty_text(self):
        self.assertEqual(ip.split_long_text(""), [])


class TestSensitive(unittest.TestCase):
    """敏感红线识别（提示不删除）。"""

    def test_hit_categories(self):
        text = "剧中出现虐杀镜头，还夹杂着算命改运的情节。"
        hits = ip.check_sensitive(text)
        self.assertIn("血腥暴力", hits)
        self.assertIn("封建迷信", hits)

    def test_no_hit(self):
        text = "少年仗剑走天涯，路见不平拔刀相助。"
        self.assertEqual(ip.check_sensitive(text), [])


class TestTemplateInjection(unittest.TestCase):
    """模板注入：{输入原文} 替换。"""

    def test_inject(self):
        template = "请根据以下内容拆分剧本：\n{输入原文}"
        out = ip.inject_prompt(template, "第一集剧本内容")
        self.assertIn("{输入原文}", template)
        self.assertNotIn("{输入原文}", out)
        self.assertIn("第一集剧本内容", out)

    def test_no_placeholder_unchanged(self):
        template = "没有任何占位符"
        self.assertEqual(ip.inject_prompt(template, "x"), template)


class TestParseInput(unittest.TestCase):
    """主流程集成。"""

    def test_full_pipeline_one_line(self):
        raw = "外卖小哥获得读心术，逆袭成为商业大佬"
        result = ip.parse_input(raw, template="扩写开场：\n{输入原文}")
        self.assertEqual(result.input_type, ip.TYPE_ONE_LINE)
        self.assertTrue(result.needs_expansion)
        self.assertEqual(result.chunk_count, 1)
        self.assertEqual(len(result.rendered), 1)
        self.assertIn("外卖小哥获得读心术", result.rendered[0])

    def test_full_pipeline_outline(self):
        raw = "第一卷 开端\n第一章 相遇\n少年与少女在雨夜相遇。"
        result = ip.parse_input(raw)
        self.assertEqual(result.input_type, ip.TYPE_OUTLINE)
        self.assertFalse(result.needs_expansion)

    def test_lengths_recorded(self):
        raw = "一句话创意内容"
        result = ip.parse_input(raw)
        self.assertEqual(result.original_length, len(raw))
        self.assertGreater(result.cleaned_length, 0)


class TestLanguageDetection(unittest.TestCase):
    """输入语言检测：中文→zh、英文→en（v1.2.0 语言匹配核心）。"""

    def test_detect_chinese(self):
        self.assertEqual(ip.detect_language("外卖小哥获得读心术"), "zh")

    def test_detect_english(self):
        self.assertEqual(ip.detect_language("A rider gains telepathy"), "en")

    def test_detect_english_with_punctuation(self):
        self.assertEqual(
            ip.detect_language('He said, "I will save you!" Wait, really?'),
            "en",
        )

    def test_detect_empty_defaults_zh(self):
        self.assertEqual(ip.detect_language(""), "zh")
        self.assertEqual(ip.detect_language("   "), "zh")

    def test_parse_input_english_sets_language(self):
        text = (
            "A delivery rider named Jack gets a strange power: he can read minds. "
            "Jack follows the gangsters to a warehouse and confronts them alone."
        )
        result = ip.parse_input(text)
        self.assertEqual(result.language, "en")
        # 英文输入 -> 英文标签（Synopsis / Novel excerpt 等）
        self.assertNotIn("CJK", result.input_type_label)
        self.assertTrue(result.input_type_label.isascii())

    def test_parse_input_chinese_sets_language(self):
        result = ip.parse_input("外卖小哥获得读心术，送餐途中一次次救下陌生人。")
        self.assertEqual(result.language, "zh")
        self.assertFalse(result.input_type_label.isascii())


if __name__ == "__main__":
    unittest.main()