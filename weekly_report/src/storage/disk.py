"""Disk usage and cleanup of ignored Full Price vs Sale uploads.

The new month-named calc already ignores ``*/discounts/*`` and old weekly
Exchanges / Full_Price_vs_Sale_Wxx names. Those files still sit on the Render
disk and are the usual cause of ``[Errno 28] No space left on device``.
"""

from __future__ import annotations

import errno
import shutil
from pathlib import Path
from typing import Any, Dict, List

from weekly_report.src.metrics.full_price_excl_exchanges import FILE_TYPE as EXCL_TYPE
from weekly_report.src.metrics.pricing_history import is_accepted_pricing_filename

DISK_FULL_DETAIL = (
    "Render disk is full (no space left on device). The export on your computer is fine — "
    "the API disk cannot store another file. In Settings, delete ignored old weekly Full "
    "Price vs Sale files (month-named files in 2026-41 are kept), or increase the Render "
    "disk, then re-upload this file alone. A failed write may have left a truncated copy."
)


def is_disk_full_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return True
    return "no space left on device" in str(exc).lower()


def is_ignored_pricing_upload(path: Path) -> bool:
    """True for uploads the month-named Full Price vs Sale calc already ignores."""
    if not path.is_file() or path.name.startswith("."):
        return False
    slot = path.parent.name
    if slot == "discounts":
        return True
    if slot == EXCL_TYPE:
        return not is_accepted_pricing_filename(path.name)
    return False


def iter_raw_files(data_root: Path) -> List[Path]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    found: List[Path] = []
    for path in raw.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            found.append(path)
    return found


def _file_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _rel(data_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(data_root))
    except ValueError:
        return str(path)


def list_ignored_pricing_uploads(data_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in iter_raw_files(data_root):
        if not is_ignored_pricing_upload(path):
            continue
        rows.append({"path": _rel(data_root, path), "bytes": _file_bytes(path)})
    rows.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))
    return rows


def delete_ignored_pricing_uploads(data_root: Path) -> Dict[str, Any]:
    deleted: List[str] = []
    errors: List[str] = []
    bytes_freed = 0
    for row in list_ignored_pricing_uploads(data_root):
        path = Path(data_root) / str(row["path"])
        size = int(row["bytes"] or 0)
        try:
            path.unlink()
            deleted.append(str(row["path"]))
            bytes_freed += size
        except OSError as exc:
            errors.append(f"{row['path']}: {exc}")
    return {
        "deleted": deleted,
        "count": len(deleted),
        "bytes_freed": bytes_freed,
        "errors": errors,
    }


def disk_usage_payload(data_root: Path) -> Dict[str, Any]:
    root = Path(data_root)
    probe = root if root.exists() else Path("/")
    try:
        usage = shutil.disk_usage(probe)
        total, used, free = int(usage.total), int(usage.used), int(usage.free)
    except OSError:
        total = used = free = 0
    files = [
        {
            "path": _rel(root, path),
            "bytes": _file_bytes(path),
            "ignored": is_ignored_pricing_upload(path),
        }
        for path in iter_raw_files(root)
    ]
    files.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))
    ignored = [row for row in files if row["ignored"]]
    used_pct = round(100.0 * used / total, 1) if total else None
    near_full = bool(free < 50 * 1024 * 1024 or (total and used / total >= 0.90))
    return {
        "data_root": str(root),
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_pct": used_pct,
        "raw_bytes": sum(int(row["bytes"]) for row in files),
        "ignored_bytes": sum(int(row["bytes"]) for row in ignored),
        "ignored_count": len(ignored),
        "near_full": near_full,
        "largest": files[:15],
        "ignored_files": ignored,
    }
