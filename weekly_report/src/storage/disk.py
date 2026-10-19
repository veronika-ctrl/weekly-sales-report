"""Disk usage and cleanup of ignored Full Price vs Sale uploads.

The new month-named calc already ignores ``*/discounts/*`` and old weekly
Exchanges / Full_Price_vs_Sale_Wxx names. Those files still sit on the Render
disk and are the usual cause of ``[Errno 28] No space left on device``.
"""

from __future__ import annotations

import errno
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from weekly_report.src.metrics.full_price_excl_exchanges import FILE_TYPE as EXCL_TYPE
from weekly_report.src.metrics.pricing_history import is_accepted_pricing_filename

DISK_FULL_DETAIL = (
    "Render disk is full (no space left on device). The export on your computer is fine — "
    "the API disk cannot store another file. In Settings, delete weeks 2026-36 to 2026-40 "
    "(Qlik/DEMA/Shopify for those weeks) and ignored old Full Price files. Month-named "
    "2026-41 files and aMER/retention/CAC/Klaviyo history are kept. Then re-upload this "
    "file alone. A failed write may have left a truncated copy."
)

# Weekly Qlik/DEMA/Shopify for these ISO weeks is the bulk of the 1 GB Render disk.
STALE_WEEKS = tuple(f"2026-{week:02d}" for week in range(36, 41))
KEEP_HISTORY_SLOTS = frozenset(
    {
        "shopify_customers",
        "retention_customers",
        "klaviyo_email",
        "cac_payback_groups",
        "cac_payback_segments",
        "cac_payback_horizon",
    }
)
AMER_SLOTS = frozenset({"amer_revenue", "amer_spend", "amer_gm2"})
_MONTH_IN_NAME = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])")
_ISO_WEEK_DIR = re.compile(r"^\d{4}-\d{2}$")


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


def is_kept_across_weeks(path: Path) -> bool:
    """History files other reports still scan from any week folder."""
    slot = path.parent.name
    if slot in KEEP_HISTORY_SLOTS:
        return True
    if slot in AMER_SLOTS and _MONTH_IN_NAME.search(path.name):
        return True
    if slot == EXCL_TYPE and is_accepted_pricing_filename(path.name):
        return True
    return False


def stale_week_files(data_root: Path) -> List[Path]:
    raw = Path(data_root) / "raw"
    found: List[Path] = []
    for week in STALE_WEEKS:
        week_dir = raw / week
        if not week_dir.is_dir():
            continue
        for path in week_dir.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                found.append(path)
    return found


def list_stale_week_deletes(data_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in stale_week_files(data_root):
        if is_kept_across_weeks(path):
            continue
        rows.append({"path": _rel(data_root, path), "bytes": _file_bytes(path)})
    rows.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))
    return rows


def _shelter_week(data_root: Path) -> str:
    raw = Path(data_root) / "raw"
    if (raw / "2026-41").exists():
        return "2026-41"
    if raw.exists():
        others = sorted(
            p.name
            for p in raw.iterdir()
            if p.is_dir() and _ISO_WEEK_DIR.match(p.name) and p.name not in STALE_WEEKS
        )
        if others:
            return others[-1]
    return "2026-41"


def _prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        root.rmdir()
    except OSError:
        pass


def delete_stale_weeks_36_to_40(data_root: Path) -> Dict[str, Any]:
    """Remove W36–W40 weekly Qlik/DEMA/Shopify. Keep history files, moved into 2026-41."""
    raw = Path(data_root) / "raw"
    shelter = _shelter_week(data_root)
    deleted: List[str] = []
    moved: List[str] = []
    errors: List[str] = []
    bytes_freed = 0
    for path in stale_week_files(data_root):
        rel = _rel(data_root, path)
        size = _file_bytes(path)
        if is_kept_across_weeks(path):
            dest = raw / shelter / path.parent.name / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                if dest.resolve() == path.resolve():
                    continue
                if dest.exists():
                    path.unlink()
                    moved.append(f"{rel} (already in {shelter})")
                else:
                    shutil.copy2(path, dest)
                    path.unlink()
                    moved.append(f"{rel} -> {shelter}/{path.parent.name}/{path.name}")
            except OSError as exc:
                errors.append(f"{rel}: {exc}")
            continue
        try:
            path.unlink()
            deleted.append(rel)
            bytes_freed += size
        except OSError as exc:
            errors.append(f"{rel}: {exc}")
    for week in STALE_WEEKS:
        _prune_empty_dirs(raw / week)
    return {
        "deleted": deleted,
        "moved": moved,
        "count": len(deleted),
        "bytes_freed": bytes_freed,
        "shelter_week": shelter,
        "errors": errors,
    }


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
    stale = list_stale_week_deletes(root)
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
        "stale_weeks": list(STALE_WEEKS),
        "stale_week_bytes": sum(int(row["bytes"]) for row in stale),
        "stale_week_count": len(stale),
        "near_full": near_full,
        "largest": files[:15],
        "ignored_files": ignored,
    }
