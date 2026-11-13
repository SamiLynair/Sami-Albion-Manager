"""Offline item-index lookup for Photon events.

The game's harvest payload contains a numeric item index, not an item name.
This module reads the local IndexedItems.json reference cache. Nothing is
downloaded while tracking and Statistics Analysis need not be running.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


MAX_INDEX_FILE_SIZE = 40 * 1024 * 1024


def find_index_file() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    base = Path(local) / "StatisticsAnalysisTool"
    roots = list((base / "Instances").glob("*/GameFiles/IndexedItems.json"))
    roots.extend((base / "Default").glob("GameFiles/IndexedItems.json"))
    if not roots:
        return None
    try:
        return max(roots, key=lambda p: p.stat().st_mtime_ns)
    except OSError:
        return None


def load_index_file(path: str | Path) -> dict[int, str]:
    """Validate and load a locally stored numeric id -> unique item name map."""
    path = Path(path)
    if path.stat().st_size > MAX_INDEX_FILE_SIZE:
        raise ValueError("IndexedItems.json is too large")
    with path.open("r", encoding="utf-8-sig") as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError("Expected an array of indexed game items")
    mapping: dict[int, str] = {}
    for entry in records:
        if not isinstance(entry, dict):
            continue
        index = entry.get("Index")
        name = entry.get("UniqueName")
        if type(index) is int and index > 0 and isinstance(name, str) and 0 < len(name) < 151:
            mapping[index] = name
    if not mapping:
        raise ValueError("No usable indexed game items")
    return mapping
