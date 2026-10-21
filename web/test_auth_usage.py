# -*- coding: utf-8 -*-
"""M2 登入與額度測試（T13a 帳號 / T13b 額度）：signup/login/logout/refresh、額度消耗與超限。

另含 M2 整合：/convert 需登入、成功轉換消耗額度並寫歷史、額度耗盡拒絕。

使用 Flask test client，檔案存取指向工作區內臨時 data 目錄，避免污染真實資料。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as webapp
import auth
import history
import usage


class AuthUsageTest(unittest.TestCase):

    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()
        # 指向臨時資料目錄，與真實 data/ 隔離
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

    def _signup(self, email="alpha@example.com", password="secret123"):
        return self.client.post(
            "/api/auth/signup",
            json={"email": email, "password": password},
        )

    def _signup_ok(self, email="alpha@example.com", password="secret123"):
        """註冊並斷言 201，回傳響應（供取 access_token / cookie）。"""
        r = self._signup(email, password)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r

    def _login(self, email="alpha@example.com", password="secret123"):
        return self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )

    def _auth_header(self, resp):
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # ---------- T13a 帳號：註冊 ----------
    def test_signup_ok(self):
        r = self._signup_ok()
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["user"]["email"], "alpha@example.com")
        self.assertEqual(data["user"]["plan"], "free")
        self.assertIn("access_token", data)
        self.assertNotIn("password_hash", data["user"])
        # refresh cookie 已下發（HttpOnly）
        self.assertIn(auth.REFRESH_COOKIE, r.headers.get_all("Set-Cookie")[0])

    def test_signup_duplicate_email(self):
        self._signup_ok()
        r = self._signup()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error_code"], "email_exists")

    def test_signup_invalid_email(self):
        r = self.client.post(
            "/api/auth/signup", json={"email": "not-email", "password": "secret123"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error_code"], "bad_email")

    def test_signup_weak_password(self):
        r = self.client.post(
            "/api/auth/signup", json={"email": "b@example.com", "password": "123"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error_code"], "bad_password")

    def test_password_stored_hashed(self):
        self._signup_ok()
        with open(auth.USERS_FILE, "r", encoding="utf-8") as fh:
            users = json.load(fh)
        self.assertEqual(len(users), 1)
        self.assertTrue(users[0]["password_hash"].startswith("$argon2"))
        self.assertNotIn("secret123", users[0]["password_hash"])

    # ---------- T13a 帳號：登入 / 登出 ----------
    def test_login_ok(self):
        self._signup_ok()
        r = self._login()
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["user"]["email"], "alpha@example.com")

    def test_login_wrong_password(self):
        self._signup_ok()
        r = self._login(password="wrongpass")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "bad_credentials")

    def test_login_unknown_email(self):
        r = self._login(email="nobody@example.com")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "bad_credentials")

    def test_logout_revokes_refresh(self):
        self._signup_ok()
        token = self.client.get_cookie(auth.REFRESH_COOKIE).value
        r = self.client.post("/api/auth/logout")
        self.assertEqual(r.status_code, 200)
        # refresh token 已撤销，续期失败
        rr = self.client.post("/api/auth/refresh")
        self.assertEqual(rr.status_code, 401)
        self.assertEqual(rr.get_json()["error_code"], "auth_required")

    # ---------- 續期（refresh rotation） ----------
    def test_refresh_rotates_token(self):
        self._signup_ok()
        old = self.client.get_cookie(auth.REFRESH_COOKIE).value
        r = self.client.post("/api/auth/refresh")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        new_cookie = self.client.get_cookie(auth.REFRESH_COOKIE)
        self.assertIsNotNone(new_cookie)
        # 手動把舊 token 放回 cookie，驗證舊 token 已被撤銷（rotation 防重放）
        self.client.set_cookie(auth.REFRESH_COOKIE, old)
        rr = self.client.post("/api/auth/refresh")
        self.assertEqual(rr.status_code, 401)
        self.assertEqual(rr.get_json()["error_code"], "auth_required")

    def test_refresh_without_cookie(self):
        r = self.client.post("/api/auth/refresh")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    # ---------- /api/me ----------
    def test_me_requires_login(self):
        r = self.client.get("/api/me")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    def test_me_returns_user_and_usage(self):
        resp = self._signup_ok()
        r = self.client.get("/api/me", headers=self._auth_header(resp))
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["user"]["email"], "alpha@example.com")
        self.assertEqual(data["usage"]["limit"], 10)  # Free 每月 10 次
        self.assertEqual(data["usage"]["used"], 0)
        self.assertEqual(data["usage"]["remaining"], 10)

    # ---------- T13b 額度：消耗與超限 ----------
    def test_consume_success(self):
        resp = self._signup_ok()
        r = self.client.post(
            "/api/usage/consume", json={"n": 1}, headers=self._auth_header(resp)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["usage"]["used"], 1)
        self.assertEqual(data["usage"]["remaining"], 9)

    def test_consume_requires_login(self):
        r = self.client.post("/api/usage/consume", json={"n": 1})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    def test_consume_quota_exceeded(self):
        resp = self._signup_ok(email="quota@example.com")
        headers = self._auth_header(resp)
        for _ in range(10):
            r = self.client.post(
                "/api/usage/consume", json={"n": 1}, headers=headers
            )
            self.assertEqual(r.status_code, 200)
        # 第 11 次超限
        r = self.client.post(
            "/api/usage/consume", json={"n": 1}, headers=headers
        )
        self.assertEqual(r.status_code, 402)
        data = r.get_json()
        self.assertEqual(data["error_code"], "quota_exceeded")
        self.assertEqual(data["detail"]["used"], 10)
        self.assertEqual(data["detail"]["limit"], 10)
        self.assertEqual(data["detail"]["remaining"], 0)

    def test_usage_monthly_reset(self):
        resp = self._signup_ok(email="reset@example.com")
        uid = resp.get_json()["user"]["id"]
        headers = self._auth_header(resp)
        for _ in range(5):
            self.client.post(
                "/api/usage/consume", json={"n": 1}, headers=headers
            )
        self.assertEqual(usage.get_usage(uid)["used"], 5)
        # 模擬跨月：把存檔月份改到過去月
        with open(usage.USAGE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data[uid]["month"] = "2000-01"
        with open(usage.USAGE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        info = usage.get_usage(uid)
        self.assertEqual(info["used"], 0)
        self.assertEqual(info["month"], usage._now_month())

    # ---------- M2 整合：/convert 登入＋額度門控 ----------
    def test_convert_requires_login(self):
        r = self.client.post("/convert", data={"text": "少年捡到古镜。"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    def test_convert_login_consumes_quota_and_history(self):
        resp = self._signup_ok(email="convert@example.com")
        uid = resp.get_json()["user"]["id"]
        headers = self._auth_header(resp)
        r = self.client.post(
            "/convert", data={"text": "少年捡到古镜。"}, headers=headers
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        # 成功轉換：消耗 1 次額度（Free 10 → 9）
        self.assertEqual(data["usage"]["used"], 1)
        self.assertEqual(data["usage"]["remaining"], 9)
        # 寫入歷史：1 條
        rows = history.get_history(uid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["num_episodes"], 1)
        self.assertIn("cleaned_length", rows[0])

    def test_convert_rejects_when_quota_empty(self):
        resp = self._signup_ok(email="empty@example.com")
        uid = resp.get_json()["user"]["id"]
        headers = self._auth_header(resp)
        # 手動把已用次數設為額度上限（模擬本月額度耗盡）
        for _ in range(10):
            self.client.post("/api/usage/consume", json={"n": 1}, headers=headers)
        r = self.client.post(
            "/convert", data={"text": "少年捡到古镜。"}, headers=headers
        )
        self.assertEqual(r.status_code, 402)
        data = r.get_json()
        self.assertEqual(data["error_code"], "quota_exceeded")
        self.assertEqual(data["detail"]["remaining"], 0)
        # 未成功轉換：歷史保持 0 條
        self.assertEqual(history.get_history(uid), [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AuthUsageTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)