# -*- coding: utf-8 -*-
"""M2 額度管理（T13b）：用量計數與上限、月度重置、超限提示。

對應 M1-M2 開發執行規劃第四章（額度管理）與第十二章（暫定三檔）：
- Free   10 次/月
- Pro    100 次/月（M3 收費開通後啟用）
- Studio 500 次/月（M3 收費開通後啟用）

存儲：web/data/usage.json
結構：{user_id: {"month": "YYYY-MM", "used": n, "plan": "free"}}

月度重置為惰性：讀取時若月份與當前不同，自動歸零並更新月份。
"""

import json
import os
import threading
from datetime import datetime, timezone

# ---------- 常數 ----------
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, "data")
USAGE_FILE = os.path.join(DATA_DIR, "usage.json")

# 暫定三檔月度額度（第十二章；Pro/Studio 於 M3 收費開通後啟用）
PLANS = {
    "free": {"limit": 10},
    "pro": {"limit": 100},
    "studio": {"limit": 500},
}

_lock = threading.Lock()


class UsageError(Exception):
    """額度不足等用量錯誤。"""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def _now_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load():
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def _save(data: dict):
    _ensure_dir()
    tmp = f"{USAGE_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, USAGE_FILE)


def plan_limit(plan: str) -> int:
    return PLANS.get(plan or "free", {}).get("limit", PLANS["free"]["limit"])


def get_usage(user_id: str) -> dict:
    """回傳目前月份用量；跨月自動歸零。"""
    month = _now_month()
    with _lock:
        usage = _load()
        row = usage.get(user_id)
        if not row or row.get("month") != month:
            row = {"month": month, "used": 0, "plan": "free"}
            usage[user_id] = row
            _save(usage)
        return {
            "month": row.get("month"),
            "used": row.get("used", 0),
            "limit": plan_limit(row.get("plan", "free")),
            "remaining": plan_limit(row.get("plan", "free")) - row.get("used", 0),
            "plan": row.get("plan", "free"),
        }


def set_plan(user_id: str, plan: str) -> dict:
    """設定方案（M3 付費開通後由計費模組呼叫）。"""
    if plan not in PLANS:
        raise UsageError("bad_plan", "不支援的方案")
    month = _now_month()
    with _lock:
        usage = _load()
        row = usage.get(user_id) or {"used": 0}
        row.update({"month": month, "plan": plan})
        usage[user_id] = row
        _save(usage)
        return {
            "month": month,
            "used": row.get("used", 0),
            "limit": plan_limit(plan),
            "plan": plan,
        }


def consume(user_id: str, n: int = 1) -> dict:
    """消耗用量；超限拋 UsageError('quota_exceeded')，提示剩餘額度。

    n 為消耗次數（目前每一次文轉劇轉換消耗 1 次）。
    """
    if n <= 0:
        raise UsageError("bad_amount", "消耗次數需為正整數")
    month = _now_month()
    with _lock:
        usage = _load()
        row = usage.get(user_id)
        if not row or row.get("month") != month:
            row = {"month": month, "used": 0, "plan": "free"}
        limit = plan_limit(row.get("plan", "free"))
        current = row.get("used", 0)
        if current + n > limit:
            raise UsageError(
                "quota_exceeded",
                "本月額度已用完，請下月再試或升級方案",
                {"used": current, "limit": limit, "remaining": max(limit - current, 0)},
            )
        row["used"] = current + n
        usage[user_id] = row
        _save(usage)
        return {
            "month": month,
            "used": row["used"],
            "limit": limit,
            "remaining": limit - row["used"],
            "plan": row.get("plan", "free"),
        }


def reset_monthly(user_id: str) -> dict:
    """手動歸零當月用量（測試/管理用）。"""
    month = _now_month()
    with _lock:
        usage = _load()
        row = usage.get(user_id) or {}
        row.update({"month": month, "used": 0, "plan": row.get("plan", "free")})
        usage[user_id] = row
        _save(usage)
        return {
            "month": month,
            "used": 0,
            "limit": plan_limit(row.get("plan", "free")),
            "plan": row.get("plan", "free"),
        }