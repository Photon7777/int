import os
from typing import Optional
import pandas as pd
import uuid

TRACKER_CSV = "tracker.csv"

HEADERS = [
    "Date Applied", "Company", "Role", "Job Link", "Location",
    "Status", "Follow-up Date", "Contact Name", "Contact Link", "Notes"
]

def ensure_tracker_exists() -> None:
    if not os.path.exists(TRACKER_CSV):
        pd.DataFrame(columns=HEADERS).to_csv(TRACKER_CSV, index=False)

def read_tracker_df() -> pd.DataFrame:
    ensure_tracker_exists()
    return pd.read_csv(TRACKER_CSV)

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected columns exist and are ordered."""
    df = df.copy()
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""
    df = df[HEADERS]
    return df

def append_row(row: dict) -> None:
    ensure_tracker_exists()
    df = read_tracker_df()
    df = normalize_df(df)
    new_df = pd.DataFrame([row])
    new_df = normalize_df(new_df)
    out = pd.concat([df, new_df], ignore_index=True)
    out.to_csv(TRACKER_CSV, index=False)

def replace_tracker_with_df(df_uploaded: pd.DataFrame) -> None:
    df_uploaded = normalize_df(df_uploaded)
    df_uploaded.to_csv(TRACKER_CSV, index=False)

def merge_tracker_with_df(df_uploaded: pd.DataFrame, dedupe: bool = True) -> None:
    ensure_tracker_exists()
    current = normalize_df(read_tracker_df())
    incoming = normalize_df(df_uploaded)

    merged = pd.concat([current, incoming], ignore_index=True)

    if dedupe:
        # De-dupe using common-sense keys (you can tweak)
        merged = merged.drop_duplicates(subset=["Company", "Role", "Job Link", "Date Applied"], keep="last")

    merged.to_csv(TRACKER_CSV, index=False)

def overwrite_tracker_df(df: pd.DataFrame) -> None:
    """Overwrite tracker.csv with the provided dataframe."""
    df.to_csv(TRACKER_CSV, index=False)

def ensure_row_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure every row has a stable _row_id. If missing, create.
    Keeps _row_id as the first column.
    """
    df = df.copy()
    if "_row_id" not in df.columns:
        df.insert(0, "_row_id", [str(uuid.uuid4()) for _ in range(len(df))])
    else:
        df["_row_id"] = df["_row_id"].fillna("").astype(str)
        missing = df["_row_id"].str.strip() == ""
        if missing.any():
            df.loc[missing, "_row_id"] = [str(uuid.uuid4()) for _ in range(missing.sum())]

        # move to front
        cols = ["_row_id"] + [c for c in df.columns if c != "_row_id"]
        df = df[cols]
    return df

def delete_rows_by_ids(row_ids: list) -> None:
    """Delete rows whose _row_id is in row_ids."""
    ensure_tracker_exists()
    df = pd.read_csv(TRACKER_CSV)
    df = ensure_row_ids(df)
    row_ids = set([str(x) for x in row_ids])
    df = df[~df["_row_id"].isin(row_ids)]
    df.to_csv(TRACKER_CSV, index=False)