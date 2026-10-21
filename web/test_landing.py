# -*- coding: utf-8 -*-
"""落地页新增功能验证：/landing 渲染、/subscribe 写入、限宽规则、工具页回归影响。"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as webapp


def brace_blocks(css):
    """按花括号计数法拆分 @media 顶层块，返回 [(media_query, body)]。"""
    blocks = []
    for m in re.finditer(r"@media\s*([^{]+)\{", css):
        i = m.end() - 1
        depth = 1
        j = i + 1
        while j < len(css) and depth > 0:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        blocks.append((m.group(1).strip(), css[i:j - 1]))
    return blocks


class LandingTest(unittest.TestCase):

    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()
        # 订阅写入指向临时文件，避免污染工程 data/
        self.tmpdir = tempfile.TemporaryDirectory()
        self.sub_file = os.path.join(self.tmpdir.name, "subscribers.json")
        webapp.SUBSCRIBERS_FILE = self.sub_file

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---- 1. 模板与路由渲染 ----
    def test_landing_renders_ok(self):
        r = self.client.get("/landing")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        # 无 Jinja 错误（未渲染的模板变量 / 未转义的故障标志）
        self.assertNotIn("{{", html)
        self.assertNotIn("jinja2", html.lower())
        self.assertIn("純文轉劇本分鏡", html)
        self.assertIn("立即免費使用", html)

    def test_landing_body_no_tool_class(self):
        html = self.client.get("/landing").get_data(as_text=True)
        self.assertIn('body class="landing"', html)
        self.assertNotIn('class="tool"', html)
        self.assertNotIn("body.tool", html)
        # 引用 style.css 与 landing.css
        self.assertIn("style.css", html)
        self.assertIn("landing.css", html)

    def test_landing_pricing_three_tiers(self):
        html = self.client.get("/landing").get_data(as_text=True)
        self.assertIn("0 美元", html)
        self.assertIn("9 美元 / 月", html)
        self.assertIn("年付 90 美元", html)
        self.assertIn("29 美元 / 月", html)
        self.assertIn("年付 290 美元", html)
        # 收費待調整提示
        self.assertIn("待開發完成十冊後依市場調查調整", html)
        # 不使用 $ 符號（渲染約束）
        self.assertNotIn("$", html)

    def test_landing_static_assets_ok(self):
        for url in ("/static/landing.css", "/static/landing.js",
                    "/static/style.css", "/static/app.js"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)

    # ---- 2. /subscribe 寫入 email ----
    def test_subscribe_valid_email_writes_file(self):
        r = self.client.post("/subscribe", json={"email": "Tester@Example.com "})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["duplicate"])
        with open(self.sub_file, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "tester@example.com")
        self.assertIn("subscribed_at", rows[0])

    def test_subscribe_duplicate_email(self):
        self.client.post("/subscribe", json={"email": "a@b.com"})
        r = self.client.post("/subscribe", json={"email": "a@b.com"})
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["duplicate"])
        with open(self.sub_file, "r", encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)), 1)

    def test_subscribe_invalid_email(self):
        for bad in ("not-an-email", "a@b", "", "  "):
            r = self.client.post("/subscribe", json={"email": bad})
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.get_json()["error_code"], "bad_email")

    def test_subscribe_no_payload(self):
        r = self.client.post("/subscribe", json={})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error_code"], "bad_email")

    # ---- 3. 限寬規則 ----
    def test_tool_page_limited_760(self):
        with open(os.path.join(os.path.dirname(__file__), "static", "style.css"),
                  encoding="utf-8") as fh:
            css = fh.read()
        self.assertIn("body.tool .page { max-width: 760px; }", css)

    def test_landing_page_uses_breakpoints(self):
        with open(os.path.join(os.path.dirname(__file__), "static", "style.css"),
                  encoding="utf-8") as fh:
            css = fh.read()
        mqs = [int(x) for x in re.findall(r"@media \(min-width: (\d+)px\)", css)]
        self.assertEqual(mqs, sorted(mqs), "斷點應嚴格升序")
        self.assertEqual(mqs, [480, 640, 768, 1024, 1280, 1536])
        # 桌面斷點把 .page 拉寬（≥768→760 / ≥1024→920 / ≥1280→1080 / ≥1536→1200）
        blocks = {q: b for q, b in brace_blocks(css)}
        self.assertIn("max-width: 920px", blocks.get("(min-width: 1024px)", ""))
        self.assertIn("max-width: 1080px", blocks.get("(min-width: 1280px)", ""))
        self.assertIn("max-width: 1200px", blocks.get("(min-width: 1536px)", ""))
        self.assertIn("max-width: 760px", blocks.get("(min-width: 768px)", ""))

    def test_landing_css_mobile_first(self):
        with open(os.path.join(os.path.dirname(__file__), "static", "landing.css"),
                  encoding="utf-8") as fh:
            css = fh.read()
        mqs = [int(x) for x in re.findall(r"@media \(min-width: (\d+)px\)", css)]
        # 移動優先：僅 min-width、升序
        self.assertEqual(mqs, sorted(mqs))
        self.assertEqual(mqs, [640, 768])
        # 手機版（基底）單欄
        self.assertIn(".features {\n  display: grid;", css)
        self.assertNotIn("grid-template-columns: repeat(3, 1fr);", css.split("@media")[0])

    # ---- 4. 既有工具頁不受影響 ----
    def test_index_still_tool(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('<body class="tool">', html)
        self.assertIn("style.css", html)
        self.assertIn("纯文转剧本分镜", html)

    def test_convert_requires_login_after_m2_gate(self):
        # M2 整合（T7）後 /convert 接入登入門控：未登入一律 401 auth_required
        r = self.client.post("/convert", data={"text": "少年捡到古镜。"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LandingTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)