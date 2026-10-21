# -*- coding: utf-8 -*-
"""M2 帳號與登入（T13a）：argon2 密碼哈希、短期 JWT＋長期 Refresh Token。

對應 M1-M2 開發執行規劃第四章（登入）：
- Email＋密碼（argon2 加密）
- Session 短期 JWT（15 分鐘）＋長期 Refresh Token（HttpOnly Cookie）

存儲（以文件方式，與 subscribers.json 同風格）：
- web/data/users.json           帳號（email、密碼雜湊、方案、建立時間）
- web/data/refresh_tokens.json  長期 Refresh Token（SHA-256 雜湊）

安全約定：
- JWT 密鑰由環境變數 T2S_JWT_SECRET 提供；未設置時使用開發預設並印出警告，
  正式上線前必須設置。密鑰值不寫入任何檔案。
- Refresh Token 明文只存在 HttpOnly Cookie；檔案內僅存 SHA-256 雜湊。
"""

import hashlib
import json
import os
import re
import secrets
import sys
import threading
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import request
import jwt

# ---------- 常數 ----------
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REFRESH_FILE = os.path.join(DATA_DIR, "refresh_tokens.json")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=15)      # 短期 JWT
REFRESH_TOKEN_TTL = timedelta(days=30)         # 長期 Refresh Token

# 開發預設密鑰：僅本地開發用；正式上線必須以 T2S_JWT_SECRET 環境變數覆蓋
DEV_SECRET = "text2script-dev-secret-change-me"
JWT_SECRET = os.environ.get("T2S_JWT_SECRET") or DEV_SECRET
if not os.environ.get("T2S_JWT_SECRET"):
    print(
        "[auth] WARNING: T2S_JWT_SECRET 未設置，使用開發預設密鑰（僅限本地開發，"
        "正式上線前請設置環境變數）",
        file=sys.stderr,
    )

# Cookie 名稱
REFRESH_COOKIE = "t2s_refresh"
# 開發環境 http 下 secure=False；正式 HTTPS 部署設 T2S_COOKIE_SECURE=1
COOKIE_SECURE = os.environ.get("T2S_COOKIE_SECURE") == "1"

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_PASSWORD_LEN = 6
MAX_PASSWORD_LEN = 128

_lock = threading.Lock()
_ph = PasswordHasher()


class AuthError(Exception):
    """登入/註冊流程錯誤；code 供前端翻譯。"""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ---------- 檔案存取 ----------
def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, type(default)) else default
    except (ValueError, OSError):
        return default


def _save_json(path, data):
    _ensure_dir()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------- 密碼 ----------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _validate_password(password: str):
    if not password or not (MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN):
        raise AuthError(
            "bad_password",
            f"密碼長度需為 {MIN_PASSWORD_LEN}–{MAX_PASSWORD_LEN} 個字元",
        )


def _validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("bad_email", "請輸入有效的 Email 地址")
    return email


# ---------- 使用者（T13a 帳號） ----------
def _new_user_id() -> str:
    return "u_" + secrets.token_urlsafe(12)


def find_user_by_email(email: str):
    email = (email or "").strip().lower()
    for u in _load_json(USERS_FILE, []):
        if u.get("email", "").lower() == email:
            return u
    return None


def find_user_by_id(user_id: str):
    for u in _load_json(USERS_FILE, []):
        if u.get("id") == user_id:
            return u
    return None


def create_user(email: str, password: str, plan: str = "free"):
    """建立帳號；email 已存在拋 AuthError('email_exists')。"""
    email = _validate_email(email)
    _validate_password(password)
    with _lock:
        if find_user_by_email(email):
            raise AuthError("email_exists", "此 Email 已註冊，請直接登入")
        user = {
            "id": _new_user_id(),
            "email": email,
            "password_hash": hash_password(password),
            "plan": plan,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        users = _load_json(USERS_FILE, [])
        users.append(user)
        _save_json(USERS_FILE, users)
        return user


def public_user(user: dict) -> dict:
    """對外回傳的使用者資訊（永遠不含密碼雜湊）。"""
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "plan": user.get("plan", "free"),
        "created_at": user.get("created_at"),
    }


def authenticate(email: str, password: str) -> dict:
    """登入驗證；成功回傳 user，失敗拋 AuthError('bad_credentials')。"""
    email = (email or "").strip().lower()
    user = find_user_by_email(email)
    if not user or not verify_password(password or "", user.get("password_hash", "")):
        raise AuthError("bad_credentials", "Email 或密碼錯誤", status=401)
    return user


# ---------- 短期 JWT（15 分鐘） ----------
def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str):
    """驗證短期 JWT；無效/過期回傳 None。"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access" or not payload.get("sub"):
        return None
    return payload.get("sub")


# ---------- 長期 Refresh Token ----------
def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    row = {
        "token_hash": _hash_refresh(token),
        "user_id": user_id,
        "expires_at": (datetime.now(timezone.utc) + REFRESH_TOKEN_TTL).isoformat(
            timespec="seconds"
        ),
    }
    with _lock:
        rows = _load_json(REFRESH_FILE, [])
        rows = [r for r in rows if r.get("user_id") != user_id]  # 單一裝置登入
        rows.append(row)
        _save_json(REFRESH_FILE, rows)
    return token


def consume_refresh_token(token: str):
    """驗證並銷毀 Refresh Token；有效回傳 user_id，無效回傳 None。

    銷毀後使用同一 token 再次請求將失敗（rotation 防重放）。
    """
    if not token:
        return None
    token_hash = _hash_refresh(token)
    with _lock:
        rows = _load_json(REFRESH_FILE, [])
        row = next((r for r in rows if r.get("token_hash") == token_hash), None)
        if not row:
            return None
        rows.remove(row)
        _save_json(REFRESH_FILE, rows)
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except (KeyError, ValueError):
            return None
        if expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        return row.get("user_id")


def revoke_all_for_user(user_id: str):
    with _lock:
        rows = _load_json(REFRESH_FILE, [])
        rows = [r for r in rows if r.get("user_id") != user_id]
        _save_json(REFRESH_FILE, rows)


# ---------- Flask 輔助 ----------
def current_user():
    """由 Authorization: Bearer <jwt> 解析當前使用者；未登入回傳 None。"""
    header = request.headers.get("Authorization", "")
    token = None
    if header.startswith("Bearer "):
        token = header[7:].strip()
    user_id = decode_access_token(token)
    if not user_id:
        return None
    return find_user_by_id(user_id)