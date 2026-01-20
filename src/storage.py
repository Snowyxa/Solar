"""Storage helpers for Solar Pipeline.

Today we store outputs as CSV files, but this module keeps I/O in one place so
we can later swap to a database backend with minimal changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


def _ensure_parent_dir(filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)


def write_snapshot_csv(records: list[dict], filepath: Path) -> bool:
    """Write a "latest snapshot" CSV (overwrite every run)."""
    if not records:
        return False
    _ensure_parent_dir(filepath)
    pd.DataFrame(records).to_csv(filepath, index=False)
    return True


def upsert_history_csv(
    records: list[dict],
    filepath: Path,
    *,
    dedupe_subset: Sequence[str],
    sort_by: Sequence[str] | None = None,
    keep: str = "last",
) -> bool:
    """Append records to a history CSV, removing redundant duplicates.

    "Redundant" means: a row where all fields in `dedupe_subset` are identical
    to a previously saved row. This lets you keep *changes over time* without
    growing the file when nothing changed.
    """
    if not records:
        return False

    _ensure_parent_dir(filepath)
    df_new = pd.DataFrame(records)

    if filepath.exists():
        try:
            df_existing = pd.read_csv(filepath)
        except Exception:
            # If the existing file is corrupted or unreadable, start fresh.
            df_existing = pd.DataFrame()
        df = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df = df_new

    # Drop redundant duplicates based on selected "identity" columns.
    df = df.drop_duplicates(subset=list(dedupe_subset), keep=keep)

    if sort_by:
        # Stable sort for nicer browsing in Excel/CSV viewers.
        df = df.sort_values(list(sort_by)).reset_index(drop=True)

    df.to_csv(filepath, index=False)
    return True

