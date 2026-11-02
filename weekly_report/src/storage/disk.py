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
    "the API disk cannot store another file. In Settings, click “Keep last 2 weeks” to delete "
    "older Qlik/DEMA/Shopify week files, then re-upload this file alone. Month-named Full Price "
    "files and aMER/retention/CAC/Klaviyo history are kept. A failed write may have left a "
    "truncated copy."
)

# Weekly Qlik/DEMA/Shopify for these ISO weeks is the bulk of the 1 GB Render disk.
STALE_WEEKS = tuple(f"2026-{week:02d}" for week in range(36, 41))
WEEKLY_BULK_SLOTS = frozenset({"qlik", "dema_spend", "dema_gm2", "shopify"})
# Latest Qlik exports already contain prior ISO weeks, so 2 week folders are enough.
KEEP_RECENT_WEEKLY = 2
MIN_FREE_FOR_UPLOAD_BYTES = 400 * 1024 * 1024
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


def list_iso_week_dirs(data_root: Path) -> List[str]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    weeks = [
        path.name
        for path in raw.iterdir()
        if path.is_dir() and _ISO_WEEK_DIR.match(path.name)
    ]
    weeks.sort(reverse=True)
    return weeks


def list_qlik_weeks(data_root: Path) -> List[str]:
    """ISO weeks that have a Qlik CSV/xlsx — the weeks the sales reports can open."""
    raw = Path(data_root) / "raw"
    found: List[str] = []
    for week in list_iso_week_dirs(data_root):
        slot = raw / week / "qlik"
        if not slot.is_dir():
            continue
        if any(
            child.is_file() and child.suffix.lower() in {".csv", ".xlsx", ".parquet"}
            for child in slot.iterdir()
            if not child.name.startswith(".")
        ):
            found.append(week)
    return found


def _qlik_cache_dir(data_root: Path) -> Path:
    return Path(data_root) / "cache" / "qlik-columns"


def prune_qlik_column_cache(data_root: Path) -> Dict[str, Any]:
    """Drop regenerated Qlik column pickles so they cannot eat the 1 GB disk."""
    cache_dir = _qlik_cache_dir(data_root)
    deleted: List[str] = []
    bytes_freed = 0
    if not cache_dir.exists():
        return {"deleted": deleted, "count": 0, "bytes_freed": 0}
    for path in cache_dir.rglob("*"):
        if not path.is_file():
            continue
        size = _file_bytes(path)
        try:
            path.unlink()
            deleted.append(_rel(Path(data_root), path))
            bytes_freed += size
        except OSError:
            continue
    _prune_empty_dirs(cache_dir)
    return {"deleted": deleted, "count": len(deleted), "bytes_freed": bytes_freed}


def _weeks_to_keep(data_root: Path, keep_last: int, extra_keep: tuple[str, ...] = ()) -> List[str]:
    weeks = list_iso_week_dirs(data_root)
    extras = [week for week in extra_keep if week]
    newest = [week for week in weeks if week not in extras][:keep_last]
    return list(dict.fromkeys(extras + newest))


def old_weekly_bulk_files(
    data_root: Path, keep_last: int = KEEP_RECENT_WEEKLY, extra_keep: tuple[str, ...] = ()
) -> List[Path]:
    """Qlik/DEMA/Shopify in week folders older than the kept set."""
    raw = Path(data_root) / "raw"
    keep = set(_weeks_to_keep(data_root, keep_last, extra_keep))
    found: List[Path] = []
    for week in list_iso_week_dirs(data_root):
        if week in keep:
            continue
        week_dir = raw / week
        for path in week_dir.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.parent.name in WEEKLY_BULK_SLOTS or is_ignored_pricing_upload(path):
                found.append(path)
    return found


def list_old_weekly_bulk_deletes(
    data_root: Path, keep_last: int = KEEP_RECENT_WEEKLY, extra_keep: tuple[str, ...] = ()
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in old_weekly_bulk_files(data_root, keep_last, extra_keep):
        if is_kept_across_weeks(path):
            continue
        rows.append({"path": _rel(data_root, path), "bytes": _file_bytes(path)})
    rows.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))
    return rows


def delete_old_weekly_bulk(
    data_root: Path, keep_last: int = KEEP_RECENT_WEEKLY, extra_keep: tuple[str, ...] = ()
) -> Dict[str, Any]:
    """Remove old weekly Qlik/DEMA/Shopify. Keep history files, moved into the newest kept week."""
    raw = Path(data_root) / "raw"
    keep = _weeks_to_keep(data_root, keep_last, extra_keep)
    shelter = next((week for week in keep if (raw / week).exists()), keep[0] if keep else "2026-41")
    deleted: List[str] = []
    moved: List[str] = []
    errors: List[str] = []
    bytes_freed = 0
    for path in old_weekly_bulk_files(data_root, keep_last, extra_keep):
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
    keep_set = set(keep)
    for week in list_iso_week_dirs(data_root):
        if week not in keep_set:
            _prune_empty_dirs(raw / week)
    cache = prune_qlik_column_cache(data_root)
    bytes_freed += int(cache.get("bytes_freed") or 0)
    return {
        "deleted": deleted,
        "moved": moved,
        "count": len(deleted),
        "bytes_freed": bytes_freed,
        "kept_weeks": keep,
        "shelter_week": shelter,
        "cache_deleted": cache.get("count") or 0,
        "errors": errors,
    }


def _disk_free_bytes(data_root: Path) -> int:
    root = Path(data_root)
    probe = root if root.exists() else Path("/")
    try:
        return int(shutil.disk_usage(probe).free)
    except OSError:
        return 0


def ensure_upload_space(
    data_root: Path, extra_keep: tuple[str, ...] = ()
) -> Dict[str, Any]:
    """Free old weekly bulk files when the 1 GB disk cannot take another Qlik export."""
    free = _disk_free_bytes(data_root)
    if free >= MIN_FREE_FOR_UPLOAD_BYTES:
        return {"pruned": False, "bytes_freed": 0, "free_before": free, "kept_weeks": []}
    result = delete_old_weekly_bulk(data_root, KEEP_RECENT_WEEKLY, extra_keep)
    free_after = _disk_free_bytes(data_root)
    if free_after < MIN_FREE_FOR_UPLOAD_BYTES:
        tighter = delete_old_weekly_bulk(data_root, 1, extra_keep)
        result["deleted"] = list(result.get("deleted") or []) + list(tighter.get("deleted") or [])
        result["moved"] = list(result.get("moved") or []) + list(tighter.get("moved") or [])
        result["count"] = len(result["deleted"])
        result["bytes_freed"] = int(result.get("bytes_freed") or 0) + int(tighter.get("bytes_freed") or 0)
        result["kept_weeks"] = tighter.get("kept_weeks") or result.get("kept_weeks")
        result["shelter_week"] = tighter.get("shelter_week") or result.get("shelter_week")
        result["cache_deleted"] = int(result.get("cache_deleted") or 0) + int(
            tighter.get("cache_deleted") or 0
        )
        result["errors"] = list(result.get("errors") or []) + list(tighter.get("errors") or [])
        free_after = _disk_free_bytes(data_root)
    result["pruned"] = True
    result["free_before"] = free
    result["free_after"] = free_after
    return result


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
    old_weekly = list_old_weekly_bulk_deletes(root)
    qlik_weeks = list_qlik_weeks(root)
    cache_dir = _qlik_cache_dir(root)
    cache_bytes = 0
    if cache_dir.exists():
        cache_bytes = sum(_file_bytes(path) for path in cache_dir.rglob("*") if path.is_file())
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
        "old_weeks": sorted({row["path"].split("/")[1] for row in old_weekly if "/" in row["path"]}),
        "old_week_bytes": sum(int(row["bytes"]) for row in old_weekly),
        "old_week_count": len(old_weekly),
        "kept_weeks": _weeks_to_keep(root, KEEP_RECENT_WEEKLY),
        "qlik_weeks": qlik_weeks,
        "latest_qlik_week": qlik_weeks[0] if qlik_weeks else None,
        "cache_bytes": cache_bytes,
        "near_full": near_full,
        "largest": files[:15],
        "ignored_files": ignored,
    }
