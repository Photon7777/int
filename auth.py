# auth.py
import re
import sqlite3
from pathlib import Path

import bcrypt

DB_PATH = Path("tracker.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_auth() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password_hash BLOB NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


def validate_username(user_id: str) -> None:
    user_id = (user_id or "").strip()
    if len(user_id) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(user_id) > 32:
        raise ValueError("Username must be at most 32 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", user_id):
        raise ValueError("Username can only contain letters, numbers, and underscore (_).")


def validate_password(password: str) -> None:
    if password is None:
        raise ValueError("Password required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")


def user_exists(user_id: str) -> bool:
    init_auth()
    conn = get_conn()
    cur = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def create_user(user_id: str, password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    validate_username(user_id)
    validate_password(password)

    if user_exists(user_id):
        raise ValueError("That username is already taken.")

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    conn = get_conn()
    conn.execute(
        "INSERT INTO users (user_id, password_hash) VALUES (?, ?)",
        (user_id, pw_hash),
    )
    conn.commit()
    conn.close()


def verify_user(user_id: str, password: str) -> bool:
    init_auth()
    user_id = (user_id or "").strip()
    if not user_id or not password:
        return False

    conn = get_conn()
    cur = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ? LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    stored_hash = row[0]
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash)

def change_password(user_id: str, current_password: str, new_password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    if not verify_user(user_id, current_password):
        raise ValueError("Current password is incorrect.")
    validate_password(new_password)

    pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (pw_hash, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id: str, current_password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    if not verify_user(user_id, current_password):
        raise ValueError("Password is incorrect.")

    conn = get_conn()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()