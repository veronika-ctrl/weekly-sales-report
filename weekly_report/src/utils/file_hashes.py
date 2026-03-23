"""File hashes for cache invalidation: same week + same files => reuse Supabase cache."""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def get_file_hashes_for_week(week: str, data_root: Path) -> Dict[str, str]:
    """
    Build a dict of file identifiers -> hash (path:mtime) for the week's raw data.
    Used to decide whether cached weekly_report_metrics can be reused.
    """
    out: Dict[str, str] = {}
    raw_dir = data_root / "raw" / week
    if not raw_dir.exists():
        return out
    for path in raw_dir.rglob("*"):
        if path.is_file():
            try:
                rel = path.relative_to(raw_dir)
                key = str(rel).replace("\\", "/")
                out[key] = f"{path.stat().st_mtime}"
            except (OSError, ValueError):
                continue
    return out


def hashes_match(
    stored: Optional[Dict[str, Any]],
    current: Dict[str, str]
) -> bool:
    """
    Return True if stored file_hashes (from Supabase) match current file hashes.
    stored may be a dict or None; if from DB it might be a JSON string (caller parses).
    """
    if not current:
        return True
    if stored is None:
        return False
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except (TypeError, ValueError):
            return False
    if not isinstance(stored, dict):
        return False
    if set(stored.keys()) != set(current.keys()):
        return False
    return all(stored.get(k) == current.get(k) for k in current)
