# db_store.py
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

DB_PATH = Path("tracker.db")

COLUMNS = [
    "_row_id",
    "user_id",
    "Date Applied",
    "Company",
    "Role",
    "Job Link",
    "Location",
    "Status",
    "Follow-up Date",
    "Contact Name",
    "Contact Link",
    "Notes",
]

TEXT_COLS = [
    "Date Applied",
    "Company",
    "Role",
    "Job Link",
    "Location",
    "Status",
    "Follow-up Date",
    "Contact Name",
    "Contact Link",
    "Notes",
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            _row_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            "Date Applied" TEXT,
            "Company" TEXT,
            "Role" TEXT,
            "Job Link" TEXT,
            "Location" TEXT,
            "Status" TEXT,
            "Follow-up Date" TEXT,
            "Contact Name" TEXT,
            "Contact Link" TEXT,
            "Notes" TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON applications(user_id);")
    conn.commit()
    conn.close()


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure all expected columns exist
    for c in TEXT_COLS:
        if c not in df.columns:
            df[c] = ""

    # Normalize types to strings (prevents streamlit editor dtype issues)
    for c in TEXT_COLS:
        df[c] = df[c].fillna("").astype(str)

    # Keep only known columns (excluding user_id/_row_id which are handled separately)
    keep = ["_row_id"] + TEXT_COLS
    for c in keep:
        if c not in df.columns:
            df[c] = ""
    return df[keep]


def ensure_row_ids(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "_row_id" not in df.columns:
        df.insert(0, "_row_id", [str(uuid.uuid4()) for _ in range(len(df))])
    else:
        df["_row_id"] = df["_row_id"].fillna("").astype(str)
        missing = df["_row_id"].str.strip() == ""
        if missing.any():
            df.loc[missing, "_row_id"] = [str(uuid.uuid4()) for _ in range(missing.sum())]
    return df


def read_tracker_df(user_id: str) -> pd.DataFrame:
    init_db()
    conn = get_conn()
    cur = conn.execute(
        'SELECT _row_id, "Date Applied","Company","Role","Job Link","Location","Status","Follow-up Date","Contact Name","Contact Link","Notes" '
        "FROM applications WHERE user_id = ? ORDER BY rowid DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["_row_id"] + TEXT_COLS)

    cols = ["_row_id"] + TEXT_COLS
    df = pd.DataFrame(rows, columns=cols)
    df = _normalize_df(df)
    df = ensure_row_ids(df)
    return df


def append_row(user_id: str, row: Dict) -> None:
    init_db()
    row_id = str(uuid.uuid4())

    # normalize
    values = {c: str(row.get(c, "") or "") for c in TEXT_COLS}

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO applications (
            _row_id, user_id, "Date Applied","Company","Role","Job Link","Location","Status",
            "Follow-up Date","Contact Name","Contact Link","Notes"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row_id,
            user_id,
            values["Date Applied"],
            values["Company"],
            values["Role"],
            values["Job Link"],
            values["Location"],
            values["Status"],
            values["Follow-up Date"],
            values["Contact Name"],
            values["Contact Link"],
            values["Notes"],
        ),
    )
    conn.commit()
    conn.close()


def overwrite_tracker_for_user(user_id: str, df: pd.DataFrame) -> None:
    """
    Replace the user's entire tracker with the rows in df.
    df must contain _row_id + TEXT_COLS.
    """
    init_db()
    df = ensure_row_ids(_normalize_df(df))

    conn = get_conn()
    conn.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))

    insert_sql = """
        INSERT INTO applications (
            _row_id, user_id, "Date Applied","Company","Role","Job Link","Location","Status",
            "Follow-up Date","Contact Name","Contact Link","Notes"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    data = []
    for _, r in df.iterrows():
        data.append(
            (
                str(r["_row_id"]),
                user_id,
                str(r["Date Applied"] or ""),
                str(r["Company"] or ""),
                str(r["Role"] or ""),
                str(r["Job Link"] or ""),
                str(r["Location"] or ""),
                str(r["Status"] or ""),
                str(r["Follow-up Date"] or ""),
                str(r["Contact Name"] or ""),
                str(r["Contact Link"] or ""),
                str(r["Notes"] or ""),
            )
        )

    conn.executemany(insert_sql, data)
    conn.commit()
    conn.close()


def merge_uploaded_csv(
    user_id: str, uploaded_df: pd.DataFrame, dedupe: bool = True
) -> None:
    existing = read_tracker_df(user_id)
    uploaded_df = ensure_row_ids(_normalize_df(uploaded_df))

    combined = pd.concat([existing, uploaded_df], ignore_index=True)

    if dedupe:
        # de-dupe by these fields (same as your UI)
        key_cols = ["Company", "Role", "Job Link", "Date Applied"]
        for c in key_cols:
            if c not in combined.columns:
                combined[c] = ""
        combined = combined.drop_duplicates(subset=key_cols, keep="first")

    overwrite_tracker_for_user(user_id, combined)


def replace_with_uploaded_csv(user_id: str, uploaded_df: pd.DataFrame) -> None:
    uploaded_df = ensure_row_ids(_normalize_df(uploaded_df))
    overwrite_tracker_for_user(user_id, uploaded_df)

def delete_all_for_user(user_id: str) -> None:
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def admin_list_users() -> pd.DataFrame:
    init_db()
    conn = get_conn()
    # users table is created by auth.py, but this query is safe if it exists
    try:
        df = pd.read_sql_query(
            """
            SELECT u.user_id,
                   u.created_at,
                   COUNT(a._row_id) AS jobs_count
            FROM users u
            LEFT JOIN applications a ON a.user_id = u.user_id
            GROUP BY u.user_id, u.created_at
            ORDER BY jobs_count DESC, u.user_id ASC
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame(columns=["user_id", "created_at", "jobs_count"])
    conn.close()
    return df