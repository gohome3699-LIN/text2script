# -*- coding: utf-8 -*-
"""M1 T4 來源與轉換追蹤：來源捕捉存檔、轉換事件記錄、渠道統計查詢。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as webapp
import auth
import history
import tracking
import usage


class TrackingTest(unittest.TestCase):

    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()
        self.tmpdir = tempfile.TemporaryDirectory()
        # 所有文件存儲重定向到臨時目錄，避免污染工程 data/
        auth.DATA_DIR = self.tmpdir.name
        auth.USERS_FILE = os.path.join(self.tmpdir.name, "users.json")
        auth.REFRESH_FILE = os.path.join(self.tmpdir.name, "refresh_tokens.json")
        usage.DATA_DIR = self.tmpdir.name
        usage.USAGE_FILE = os.path.join(self.tmpdir.name, "usage.json")
        history.DATA_DIR = self.tmpdir.name
        history.HISTORY_FILE = os.path.join(self.tmpdir.name, "history.json")
        tracking.DATA_DIR = self.tmpdir.name
        tracking.TRACKING_FILE = os.path.join(self.tmpdir.name, "tracking.json")
        webapp.SUBSCRIBERS_FILE = os.path.join(self.tmpdir.name, "subscribers.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _read_tracking(self):
        if not os.path.exists(tracking.TRACKING_FILE):
            return []
        with open(tracking.TRACKING_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)["events"]

    def _signup(self, email="s@example.com", password="secret123", source=None):
        payload = {"email": email, "password": password}
        if source is not None:
            payload["source"] = source
        r = self.client.post("/api/auth/signup", json=payload)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    # ---- 1. 訂閱來源存檔 ----
    def test_subscribe_stores_source(self):
        r = self.client.post("/subscribe", json={
            "email": "a@b.com",
            "source": {
                "utm_source": "fb",
                "utm_medium": "cpc",
                "utm_campaign": "cold_start",
                "referrer": "https://facebook.com/x",
                "page": "/landing",
            },
        })
        self.assertEqual(r.status_code, 200)
        with open(webapp.SUBSCRIBERS_FILE, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        self.assertEqual(len(rows), 1)
        src = rows[0]["source"]
        self.assertEqual(src["utm_source"], "fb")
        self.assertEqual(src["utm_medium"], "cpc")
        self.assertEqual(src["utm_campaign"], "cold_start")
        self.assertEqual(src["referrer"], "https://facebook.com/x")
        self.assertEqual(src["page"], "/landing")

    def test_subscribe_without_source_ok(self):
        r = self.client.post("/subscribe", json={"email": "a@b.com"})
        self.assertEqual(r.status_code, 200)
        with open(webapp.SUBSCRIBERS_FILE, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        self.assertIsNone(rows[0].get("source"))

    def test_subscribe_filters_non_whitelist_source(self):
        r = self.client.post("/subscribe", json={
            "email": "a@b.com",
            "source": {"utm_source": "fb", "hacker": "x" * 999},
        })
        self.assertEqual(r.status_code, 200)
        with open(webapp.SUBSCRIBERS_FILE, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        src = rows[0]["source"]
        self.assertEqual(src["utm_source"], "fb")
        self.assertNotIn("hacker", src)

    def test_sanitize_source_length_limit(self):
        src = tracking.sanitize_source(
            {"utm_source": "x" * 999, "page": "/landing", "utm_medium": 123}
        )
        self.assertEqual(len(src["utm_source"]), tracking.FIELD_MAX_LEN)
        self.assertEqual(src["page"], "/landing")
        self.assertNotIn("utm_medium", src)  # 非字串欄位不接收

    # ---- 2. 轉換事件 ----
    def test_subscribe_records_event(self):
        self.client.post("/subscribe", json={
            "email": "a@b.com",
            "source": {"utm_source": "google"},
        })
        events = self._read_tracking()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "subscribe")
        self.assertEqual(events[0]["email"], "a@b.com")
        self.assertEqual(events[0]["utm_source"], "google")

    def test_subscribe_duplicate_no_second_event(self):
        self.client.post("/subscribe", json={"email": "a@b.com"})
        self.client.post("/subscribe", json={"email": "a@b.com"})
        events = self._read_tracking()
        self.assertEqual(len(events), 1)

    def test_signup_records_event_with_source(self):
        self._signup(source={"utm_source": "fb"})
        events = self._read_tracking()
        self.assertEqual(events[0]["event"], "signup")
        self.assertEqual(events[0]["email"], "s@example.com")
        self.assertEqual(events[0]["utm_source"], "fb")

    def test_signup_without_source_no_event(self):
        self._signup()
        events = self._read_tracking()
        self.assertEqual(events, [])

    def test_login_records_event_with_source(self):
        self._signup()
        r = self.client.post("/api/auth/login", json={
            "email": "s@example.com",
            "password": "secret123",
            "source": {"utm_source": "google", "utm_campaign": "retarget"},
        })
        self.assertEqual(r.status_code, 200)
        events = self._read_tracking()
        self.assertEqual(events[-1]["event"], "login")
        self.assertEqual(events[-1]["utm_source"], "google")
        self.assertEqual(events[-1]["utm_campaign"], "retarget")

    def test_convert_records_event(self):
        data = self._signup("c@example.com")
        headers = {"Authorization": "Bearer " + data["access_token"]}
        r = self.client.post("/convert", data={"text": "少年捡到古镜，卷入一场千年棋局。"},
                             headers=headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        events = self._read_tracking()
        self.assertEqual(events[-1]["event"], "convert")
        self.assertEqual(events[-1]["email"], "c@example.com")
        self.assertGreater(events[-1]["num_episodes"], 0)

    # ---- 3. 統計查詢 ----
    def test_tracking_api_requires_login(self):
        r = self.client.get("/api/tracking")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "auth_required")

    def test_tracking_api_stats(self):
        self.client.post("/subscribe", json={
            "email": "a@b.com",
            "source": {"utm_source": "fb"},
        })
        self.client.post("/subscribe", json={
            "email": "b@b.com",
            "source": {"utm_source": "google"},
        })
        data = self._signup(source={"utm_source": "fb"})
        headers = {"Authorization": "Bearer " + data["access_token"]}
        r = self.client.get("/api/tracking", headers=headers)
        self.assertEqual(r.status_code, 200)
        stats = r.get_json()["stats"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_event"], {"subscribe": 2, "signup": 1})
        self.assertEqual(stats["by_source"], {"fb": 2, "google": 1})
        self.assertEqual(len(stats["recent"]), 3)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TrackingTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)