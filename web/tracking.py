# -*- coding: utf-8 -*-
"""M1 T4 來源與轉換追蹤：歸因來源捕捉、轉換事件記錄與統計。

對應 M1 完成標準「email 收集、來源與轉換追蹤」與落地頁驗證環節：
- 來源捕捉：前端把落地頁 URL 的 utm_* 參數、referrer、頁面路徑存到
  localStorage，訂閱 / 註冊 / 登入時一併提交（source 欄位），後端白名單
  校驗後寫入 subscribers.json 或追蹤事件。
- 轉換事件：subscribe / signup / login / convert 依發生時序記錄，
  用於冷啟動渠道效果評估（哪個來源貢獻的註冊與實際使用最多），
  也為 M3 收費漏斗（訂閱付款事件）預留同一事件表。

存儲：web/data/tracking.json
結構：{"events": [{"ts": "ISO8601", "event": "subscribe|signup|login|convert|...", ...}]}
保留最近 TRACKING_LIMIT 條事件（預設 2000）；查詢介面回傳最近 STATS_LIMIT 條。
"""

import json
import os
import threading
from datetime import datetime, timezone

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, "data")
TRACKING_FILE = os.path.join(DATA_DIR, "tracking.json")

TRACKING_LIMIT = 2000  # 事件總量上限（檔案方式存儲的保護）
STATS_LIMIT = 50       # 查詢介面回傳的最近事件數

# 來源欄位白名單：只接受這些欄位，避免任意欄位污染統計
SOURCE_FIELDS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "referrer",
    "page",
)
FIELD_MAX_LEN = 500

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load() -> dict:
    if not os.path.exists(TRACKING_FILE):
        return {"events": []}
    try:
        with open(TRACKING_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data
    except (ValueError, OSError):
        pass
    return {"events": []}


def _save(data: dict):
    _ensure_dir()
    tmp = f"{TRACKING_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, TRACKING_FILE)


def sanitize_source(raw) -> dict:
    """過濾來源欄位：只保留白名單內的非空字串，並限制長度。"""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in SOURCE_FIELDS:
        val = raw.get(key)
        if isinstance(val, str):
            val = val.strip()
            if val:
                out[key] = val[:FIELD_MAX_LEN]
    return out


def record_event(event: str, data: dict | None = None) -> dict:
    """記錄一筆轉換事件；回傳新事件 dict。"""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
    }
    if data:
        row.update({k: v for k, v in data.items() if v is not None})
    with _lock:
        store = _load()
        events = store["events"]
        events.append(row)
        store["events"] = events[-TRACKING_LIMIT:]
        _save(store)
    return row


def get_events(limit: int = STATS_LIMIT) -> list:
    """讀取最近事件，按時間正序（append 順序）。"""
    with _lock:
        events = _load()["events"]
    return events[-limit:]


def stats() -> dict:
    """渠道統計：總事件數、按事件類型計數、按 utm_source 計數、最近事件。"""
    with _lock:
        events = _load()["events"]
    total = len(events)
    by_event = {}
    by_source = {}
    for ev in events:
        name = ev.get("event", "unknown")
        by_event[name] = by_event.get(name, 0) + 1
        src = (ev.get("utm_source") or "").strip()
        if src:
            by_source[src] = by_source.get(src, 0) + 1
    return {
        "total": total,
        "by_event": by_event,
        "by_source": by_source,
        "recent": events[-STATS_LIMIT:],
    }