"""Upload destination rules: replace-on-upload vs accumulate siblings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import FrozenSet, List

from weekly_report.src.metrics.adjusted_amer import AMER_DEMA_FILE_TYPES, SHOPIFY_CUSTOMERS_TYPE
from weekly_report.src.metrics.cac_payback import CAC_PAYBACK_FILE_TYPES

# Slots that keep prior CSVs so week + month (or successive history) files coexist.
# Same sanitized filename in the same week folder still overwrites that one file
# (a corrected W36 replaces the test-only W36; August with a different name stays).
ACCUMULATING_FILE_TYPES: FrozenSet[str] = frozenset(
    {
        "discounts",
        "full_price_vs_sale_excl_exchanges",
        SHOPIFY_CUSTOMERS_TYPE,
        *AMER_DEMA_FILE_TYPES,
        *CAC_PAYBACK_FILE_TYPES,
    }
)

# Retention / Klaviyo / weekly Qlik+Dema+Shopify sessions: one file per slot.
REPLACE_ON_UPLOAD_FILE_TYPES: FrozenSet[str] = frozenset(
    {
        "qlik",
        "dema_spend",
        "dema_gm2",
        "shopify",
        "budget",
        "retention_customers",
        "klaviyo_email",
    }
)


_ISO_WEEK_DIR = re.compile(r"^\d{4}-\d{2}$")


def is_accumulating_file_type(file_type: str) -> bool:
    return file_type in ACCUMULATING_FILE_TYPES


def list_weeks_with_uploads(data_root: Path) -> List[str]:
    """ISO-week folders under data/raw that contain at least one uploaded file.

    Used by the week dropdown so a newly uploaded week shows as having data
    even when Supabase has not cached metrics yet. Does not open Excel/CSV.
    """
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    found: List[str] = []
    for week_dir in raw.iterdir():
        if not week_dir.is_dir() or not _ISO_WEEK_DIR.match(week_dir.name):
            continue
        has_file = False
        for slot in week_dir.iterdir():
            if not slot.is_dir():
                continue
            for child in slot.iterdir():
                if child.is_file() and not child.name.startswith("."):
                    has_file = True
                    break
            if has_file:
                break
        if has_file:
            found.append(week_dir.name)
    found.sort(reverse=True)
    return found


def sanitize_upload_filename(filename: str | None) -> str:
    raw_name = Path(filename or "upload.csv").name
    safe_stem = re.sub(r"[^\w.\-]+", "_", Path(raw_name).stem, flags=re.UNICODE).strip("._") or "upload"
    safe_suffix = Path(raw_name).suffix.lower() or ".csv"
    return f"{safe_stem}{safe_suffix}"


def list_slot_files(folder: Path) -> List[Path]:
    """Visible files in a Settings slot folder, oldest first."""
    if not folder.exists():
        return []
    files = [f for f in folder.glob("*.*") if f.is_file() and not f.name.startswith(".")]
    files.sort(key=lambda f: (f.stat().st_mtime, f.name.lower()))
    return files


def prepare_slot_for_upload(folder: Path, file_type: str, filename: str | None) -> Path:
    """Create the slot folder and return the destination path.

    Replace-on-upload types wipe every sibling first.
    Accumulating types keep siblings; a repeat of the same sanitized name overwrites
    that file only.
    """
    folder.mkdir(parents=True, exist_ok=True)
    if not is_accumulating_file_type(file_type):
        for existing in list_slot_files(folder):
            existing.unlink()
    return folder / sanitize_upload_filename(filename)
