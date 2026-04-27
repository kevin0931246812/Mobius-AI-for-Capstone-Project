"""
anomaly_manager.py
------------------
Handles loading and saving the Anomaly Archive — a persistent JSON record of
demand anomalies that have been classified and resolved by the analyst.

Archive schema (each entry):
  {
    "archive_id"  : str   — unique ID (customer + item + date, slugified)
    "archived_at" : str   — ISO timestamp of when it was archived
    "customer"    : str   — customer name
    "item"        : str   — product type (e.g. "55GAL Drum")
    "date"        : str   — date of the anomalous order (YYYY-MM-DD)
    "qty"         : int   — quantity ordered on that date
    "z_score"     : float — Z-score of the anomaly
    "reason"      : str   — analyst-selected classification
    "notes"       : str   — optional free-text analyst notes
  }
"""

import json
import os
from datetime import datetime

from config import ANOMALY_ARCHIVE_PATH as ARCHIVE_PATH

# Available classification reasons shown in the UI dropdown
ANOMALY_REASONS = [
    "Select a reason…",
    "Urgent Order",
    "Seasonal Demand",
    "Issued / Corrective Order",
    "Promotional Event",
    "Data Entry Error",
    "Other",
]


def load_archive() -> list[dict]:
    """Load all archived anomaly entries from disk. Returns an empty list if the file doesn't exist."""
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_archive(entries: list[dict]) -> None:
    """Overwrite the archive file with the given list of entries."""
    with open(ARCHIVE_PATH, "w") as f:
        json.dump(entries, f, indent=4)


def make_archive_id(customer: str, item: str, date: str) -> str:
    """
    Generate a stable unique ID for an anomaly based on customer, item, and date.
    Used to detect duplicates before adding a new entry.
    """
    slug = f"{customer}__{item}__{date}".lower().replace(" ", "_")
    return slug


def archive_anomalies(new_entries: list[dict]) -> tuple[int, int]:
    """
    Merge new anomaly classifications into the archive, skipping duplicates.

    Args:
        new_entries : List of dicts matching the archive schema.

    Returns:
        (added_count, skipped_count)
    """
    existing    = load_archive()
    existing_ids = {e["archive_id"] for e in existing}

    added   = 0
    skipped = 0
    for entry in new_entries:
        if entry["archive_id"] in existing_ids:
            skipped += 1
        else:
            existing.append(entry)
            added += 1

    if added > 0:
        save_archive(existing)

    return added, skipped


def build_archive_entry(
    customer : str,
    item     : str,
    date     : str,
    qty      : int,
    z_score  : float,
    reason   : str,
    notes    : str = "",
) -> dict:
    """Construct a single archive entry dict ready for saving."""
    return {
        "archive_id"  : make_archive_id(customer, item, date),
        "archived_at" : datetime.now().isoformat(timespec="seconds"),
        "customer"    : customer,
        "item"        : item,
        "date"        : date,
        "qty"         : qty,
        "z_score"     : z_score,
        "reason"      : reason,
        "notes"       : notes,
    }


def get_archived_ids() -> set[str]:
    """Return the set of archive IDs already stored on disk (for fast membership checks)."""
    return {e["archive_id"] for e in load_archive()}
