# -*- coding: utf-8 -*-
"""M2 前端三頁與 /api/history 測試（T8）。

驗證：
- /login、/dashboard、/usage 三頁可渲染（無 Jinja 錯誤），body 不掛 tool、
  寬版套用斷點、引用 member.css 與各自 JS；
- GET /api/history 需登入；登入後回傳轉換歷史（與 history.append_history 聯動、
  按時間倒序、不同使用者資料隔離）；
- 前端引用的靜態資源檔案皆存在。

檔案存取指向臨時 data 目錄，避免污染真實資料。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as webapp
import auth
import history
import usage


class MemberPagesTest(unittest.TestCase):

    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()
        self.tmpdir = tempfile.TemporaryDirectory()
        auth.DATA_DIR = self.tmpdir.name
        auth.USERS_FILE = os.path.join(self.tmpdir.name, "users.json")
        auth.REFRESH_FILE = os.path.join(self.tmpdir.name, "refresh_tokens.json")
        usage.DATA_DIR = self.tmpdir.name
        usage.USAGE_FILE = os.path.join(self.tmpdir.name, "usage.json")
        history.DATA_DIR = self.tmpdir.name
        history.HISTORY_FILE = os.path.join(self.tmpdir.name, "history.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _signup_ok(self, email="member@example.com", password="secret123"):
        r = self.client.post(
            "/api/auth/signup",
            json={"email": email, "password": password},
        )
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r

    def _auth_header(self, resp):
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # ---------- 三頁渲染 ----------
    def test_login_page_ok(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("登入", html)
        self.assertIn("註冊", html)
        # body 不掛 tool（寬版套用斷點），掛 member class
        self.assertNotIn('class="tool"', html)
        self.assertIn('class="member"', html)
        self.assertIn("member.css", html)
        self.assertIn("login.js", html)

    def test_dashboard_page_ok(self):
        r = self.client.get("/dashboard")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("使用概況", html)
        self.assertIn("歷史記錄", html)
        self.assertNotIn('class="tool"', html)
        self.assertIn('class="member"', html)
        self.assertIn("dashboard.js", html)

    def test_usage_page_ok(self):
        r = self.client.get("/usage")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("文轉劇", html)
        self.assertIn("convert-btn", html)
        self.assertNotIn('class="tool"', html)
        self.assertIn('class="member"', html)
        self.assertIn("usage.js", html)

    # ---------- /api/history ----------
    def test_history_requires_login(self):
        r = self.client.get("/api/history")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    def test_history_empty(self):
        resp = self._signup_ok()
        r = self.client.get("/api/history", headers=self._auth_header(resp))
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["history"], [])

    def test_history_returns_records(self):
        resp = self._signup_ok()
        headers = self._auth_header(resp)
        uid = resp.get_json()["user"]["id"]
        history.append_history(uid, {
            "cleaned_length": 320,
            "num_episodes": 1,
            "input_type": "summary",
            "language": "zh",
            "break_by_shot": False,
        })
        history.append_history(uid, {
            "cleaned_length": 950,
            "num_episodes": 3,
            "input_type": "excerpt",
            "language": "zh",
            "break_by_shot": True,
        })
        r = self.client.get("/api/history", headers=headers)
        self.assertEqual(r.status_code, 200)
        rows = r.get_json()["history"]
        self.assertEqual(len(rows), 2)
        # 時間倒序：最新在前
        self.assertEqual(rows[0]["input_type"], "excerpt")
        self.assertEqual(rows[0]["num_episodes"], 3)
        self.assertTrue(rows[0]["break_by_shot"])
        self.assertEqual(rows[1]["input_type"], "summary")

    def test_history_other_users_isolated(self):
        r1 = self._signup_ok("alice@example.com")
        r2 = self._signup_ok("bob@example.com")
        uid1 = r1.get_json()["user"]["id"]
        history.append_history(uid1, {
            "cleaned_length": 100,
            "num_episodes": 1,
            "input_type": "one_line",
            "language": "zh",
            "break_by_shot": False,
        })
        rows = self.client.get(
            "/api/history", headers=self._auth_header(r2)
        ).get_json()["history"]
        self.assertEqual(rows, [])

    # ---------- 靜態資源存在性 ----------
    def test_static_assets_exist(self):
        web_dir = os.path.dirname(os.path.abspath(__file__))
        for name in ["member.css", "auth.js", "login.js", "dashboard.js", "usage.js"]:
            self.assertTrue(
                os.path.exists(os.path.join(web_dir, "static", name)),
                f"missing static/{name}",
            )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MemberPagesTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)