import base64
import hashlib
import os
import re
import bcrypt
from cryptography.fernet import Fernet

from db import get_conn


def init_auth() -> None:
    """
    Users table for auth + preferences + per-user Gmail connection.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    password_hash BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    email TEXT,
                    notify_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
                    sender_name TEXT,
                    linkedin_url TEXT,
                    portfolio_url TEXT,
                    target_role TEXT,
                    target_location TEXT,
                    candidate_summary TEXT,
                    gmail_email TEXT,
                    gmail_token_encrypted BYTEA,
                    gmail_connected_at TIMESTAMPTZ,
                    gmail_oauth_state TEXT,
                    gmail_oauth_state_created_at TIMESTAMPTZ
                );
                """
            )
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_opt_in BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sender_name TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS target_role TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS target_location TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS candidate_summary TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_email TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_token_encrypted BYTEA;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_connected_at TIMESTAMPTZ;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_oauth_state TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_oauth_state_created_at TIMESTAMPTZ;")
        conn.commit()


def _coerce_fernet_key(secret: str) -> bytes:
    raw = (secret or "").strip().encode("utf-8")
    try:
        Fernet(raw)
        return raw
    except Exception:
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)


def _secret_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
        if secret_value:
            return str(secret_value).strip()
    except Exception:
        pass
    return ""


def _gmail_token_cipher() -> Fernet:
    secret = (
        _secret_value("GMAIL_TOKEN_ENCRYPTION_KEY")
        or _secret_value("APP_ENCRYPTION_KEY")
        or _secret_value("NEXTROLE_APP_ENCRYPTION_KEY")
        or _secret_value("DATABASE_URL")
    )
    if not secret:
        raise RuntimeError(
            "Missing token encryption secret. Set GMAIL_TOKEN_ENCRYPTION_KEY or APP_ENCRYPTION_KEY."
        )
    return Fernet(_coerce_fernet_key(secret))


def encrypt_user_gmail_token(token_json: str) -> bytes:
    return _gmail_token_cipher().encrypt((token_json or "").encode("utf-8"))


def decrypt_user_gmail_token(value) -> str:
    if value is None:
        return ""
    if isinstance(value, memoryview):
        value = value.tobytes()
    if not value:
        return ""
    return _gmail_token_cipher().decrypt(value).decode("utf-8")


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
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (user_id,))
            return cur.fetchone() is not None


def create_user(user_id: str, password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    validate_username(user_id)
    validate_password(password)

    if user_exists(user_id):
        raise ValueError("That username is already taken.")

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, password_hash) VALUES (%s, %s)",
                (user_id, pw_hash),
            )
        conn.commit()


def verify_user(user_id: str, password: str) -> bool:
    init_auth()
    user_id = (user_id or "").strip()
    if not user_id or not password:
        return False

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM users WHERE user_id = %s LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return False

    stored = row[0]
    # psycopg2 can return BYTEA as memoryview
    if isinstance(stored, memoryview):
        stored = stored.tobytes()

    return bcrypt.checkpw(password.encode("utf-8"), stored)


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()

    if not verify_user(user_id, current_password):
        raise ValueError("Current password is incorrect.")

    validate_password(new_password)
    pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE user_id = %s",
                (pw_hash, user_id),
            )
        conn.commit()


def delete_user(user_id: str, current_password: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()

    if not verify_user(user_id, current_password):
        raise ValueError("Password is incorrect.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()


def update_email_prefs(user_id: str, email: str, opt_in: bool) -> None:
    """
    Save reminder email preferences.
    """
    init_auth()
    user_id = (user_id or "").strip()
    email = (email or "").strip()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET email = %s, notify_opt_in = %s WHERE user_id = %s",
                (email if email else None, bool(opt_in), user_id),
            )
        conn.commit()


def get_email_prefs(user_id: str) -> dict:
    """
    Returns {"email": str|None, "notify_opt_in": bool}
    """
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email, notify_opt_in FROM users WHERE user_id = %s LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"email": None, "notify_opt_in": False}
    return {"email": row[0], "notify_opt_in": bool(row[1])}


def update_user_profile(
    user_id: str,
    *,
    sender_name: str = "",
    linkedin_url: str = "",
    portfolio_url: str = "",
    target_role: str = "",
    target_location: str = "",
    candidate_summary: str = "",
) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET sender_name = %s,
                    linkedin_url = %s,
                    portfolio_url = %s,
                    target_role = %s,
                    target_location = %s,
                    candidate_summary = %s
                WHERE user_id = %s
                """,
                (
                    (sender_name or "").strip(),
                    (linkedin_url or "").strip(),
                    (portfolio_url or "").strip(),
                    (target_role or "").strip(),
                    (target_location or "").strip(),
                    (candidate_summary or "").strip(),
                    user_id,
                ),
            )
        conn.commit()


def get_user_profile(user_id: str) -> dict:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sender_name, linkedin_url, portfolio_url, target_role,
                       target_location, candidate_summary
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {}
    keys = [
        "sender_name",
        "linkedin_url",
        "portfolio_url",
        "target_role",
        "target_location",
        "candidate_summary",
    ]
    return {key: row[idx] or "" for idx, key in enumerate(keys)}


def save_user_gmail_connection(user_id: str, gmail_email: str, token_json: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    gmail_email = (gmail_email or "").strip()
    encrypted = encrypt_user_gmail_token(token_json)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET gmail_email = %s,
                    gmail_token_encrypted = %s,
                    gmail_connected_at = NOW(),
                    gmail_oauth_state = NULL,
                    gmail_oauth_state_created_at = NULL
                WHERE user_id = %s
                """,
                (gmail_email, encrypted, user_id),
            )
        conn.commit()


def clear_user_gmail_connection(user_id: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET gmail_email = NULL,
                    gmail_token_encrypted = NULL,
                    gmail_connected_at = NULL,
                    gmail_oauth_state = NULL,
                    gmail_oauth_state_created_at = NULL
                WHERE user_id = %s
                """,
                (user_id,),
            )
        conn.commit()


def get_user_gmail_connection(user_id: str, include_token: bool = False) -> dict:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gmail_email, gmail_token_encrypted, gmail_connected_at
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return {"connected": False, "gmail_email": "", "connected_at": None}

    gmail_email = row[0] or ""
    token_encrypted = row[1]
    connected_at = row[2]
    connected = bool(gmail_email and token_encrypted)
    payload = {
        "connected": connected,
        "gmail_email": gmail_email,
        "connected_at": connected_at,
    }
    if include_token and connected:
        payload["token_json"] = decrypt_user_gmail_token(token_encrypted)
    return payload


def save_user_gmail_oauth_state(user_id: str, oauth_state: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    oauth_state = (oauth_state or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET gmail_oauth_state = %s,
                    gmail_oauth_state_created_at = NOW()
                WHERE user_id = %s
                """,
                (oauth_state or None, user_id),
            )
        conn.commit()


def get_user_gmail_oauth_state(user_id: str) -> str:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT gmail_oauth_state FROM users WHERE user_id = %s LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return ""
    return row[0] or ""


def clear_user_gmail_oauth_state(user_id: str) -> None:
    init_auth()
    user_id = (user_id or "").strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET gmail_oauth_state = NULL,
                    gmail_oauth_state_created_at = NULL
                WHERE user_id = %s
                """,
                (user_id,),
            )
        conn.commit()


def gmail_oauth_state_matches(
    callback_state: str,
    *,
    session_state: str = "",
    session_user: str = "",
    db_state: str = "",
    user_id: str = "",
) -> bool:
    callback_state = (callback_state or "").strip()
    session_state = (session_state or "").strip()
    session_user = (session_user or "").strip()
    db_state = (db_state or "").strip()
    user_id = (user_id or "").strip()

    valid_session_state = callback_state == session_state and session_user == user_id and bool(session_state)
    valid_db_state = callback_state == db_state and bool(db_state)
    return valid_session_state or valid_db_state
