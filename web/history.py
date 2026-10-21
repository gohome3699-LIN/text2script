# -*- coding: utf-8 -*-
"""M2 使用歷史記錄（儀表板「歷史記錄」區塊數據來源）。

存儲：web/data/history.json
結構：{user_id: [ {"ts": "...", "cleaned_length": n, "num_episodes": n,
                  "input_type": "...", "language": "zh|en", "break_by_shot": bool} ]}

保留最近 HISTORY_LIMIT 條；由 /convert（登入用戶）寫入，GET /api/history 讀取。
"""

import json
import os
import threading
from datetime import datetime, timezone

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

HISTORY_LIMIT = 50

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def _save(data: dict):
    _ensure_dir()
    tmp = f"{HISTORY_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


def append_history(user_id: str, meta: dict) -> list:
    """追加一條轉換紀錄，回傳該使用者最新列表（最多 HISTORY_LIMIT 條）。"""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cleaned_length": int(meta.get("cleaned_length", 0)),
        "num_episodes": int(meta.get("num_episodes", 0)),
        "input_type": meta.get("input_type", ""),
        "language": meta.get("language", "zh"),
        "break_by_shot": bool(meta.get("break_by_shot", False)),
    }
    with _lock:
        history = _load()
        rows = history.get(user_id, [])
        rows.insert(0, record)
        history[user_id] = rows[:HISTORY_LIMIT]
        _save(history)
        return history[user_id]


def get_history(user_id: str, limit: int = HISTORY_LIMIT) -> list:
    """讀取轉換紀錄，按時間倒序。"""
    with _lock:
        rows = _load().get(user_id, [])
        return rows[:limit]