"""Discount types (codes and manual discounts) from bundled daily CSVs.

Markdowns / lowered prices stay on the Full Price vs Sale slides.
Mapping file wins over the daily file's group/subgroup when code_or_title matches.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from weekly_report.src.fx_rates import convert_revenue_over_time_to_sek
from weekly_report.src.metrics.discounts_sales import _build_display_weeks, _iso_week_series
from weekly_report.src.periods.calculator import get_week_date_range

NOTE = (
    "Codes and manual discounts only; lowered prices (markdowns) are shown "
    "on the Full Price vs Sale slides."
)

# Display order only. Aliases match strings in the bundled mapping/daily CSVs
# (including the numeric prefix). Old labels stay as aliases so prior files still map.
DISPLAY_GROUPS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("klaviyo", "Klaviyo", ("1 Klaviyo", "Klaviyo")),
    ("customer_care", "Customer care", ("2 Customer care", "Customer care")),
    ("conjured", "Conjured referral", ("3 Conjured referral", "Conjured referral")),
    ("campaign", "Campaign codes", ("4 Campaign codes", "Campaign codes")),
    (
        "investors",
        "Investors, team, PR & friends",
        (
            "5 Investors, team, PR & friends",
            "Investors, team, PR & friends",
            "5 Internal, friends & PR",
            "5 Internal friends & PR",
            "Internal friends & PR",
        ),
    ),
    ("subscription", "Subscription codes", ("7 Subscription codes", "Subscription codes")),
    ("test", "Test orders", ("6 Test orders", "Test orders")),
    ("other", "Other / unknown", ("8 Other / unknown", "7 Other / unknown", "Other / unknown", "Other")),
    ("aftership", "AfterShip exchanges", ("0 AfterShip exchanges", "AfterShip exchanges")),
]

# Curated subgroups (payload still lists zeros; the UI hides empty rows).
# Groups without an entry still emit whatever subgroups appear in the window.
DISPLAY_SUBGROUPS: Dict[str, List[Tuple[str, str, Tuple[str, ...], bool]]] = {
    "aftership": [
        ("aftership_exchange_orders", "AfterShip exchange orders", ("AfterShip exchange orders",), False),
        ("manual_exchange_codes", "Manual exchange codes", ("Manual exchange codes",), False),
    ],
    "klaviyo": [
        ("welcome_code", "Welcome code", ("Welcome code",), False),
        ("memories", "Memories", ("Memories",), False),
        ("inactive_winback", "Inactive Winback", ("Inactive Winback",), False),
    ],
    "customer_care": [
        (
            "manual_discount",
            "Manual discount on order (draft/edit)",
            ("Manual discount on order (draft/edit)",),
            False,
        ),
        ("named_care_codes", "Named / care codes", ("Named / care codes",), False),
    ],
    "investors": [
        (
            "investors_owner_founder",
            "Investors, owner & founder",
            ("Investors, owner & founder",),
            False,
        ),
        ("team", "Team", ("Team",), False),
        ("pr", "PR", ("PR",), False),
        (
            "marketing_creative",
            "Marketing (creative team)",
            ("Marketing (creative team)",),
            False,
        ),
        ("friends_family", "Friends & family", ("Friends & family",), False),
        (
            "other_named",
            "Other named codes (to confirm)",
            ("Other named codes (to confirm)",),
            False,
        ),
    ],
}

KLAVIYO_SUBGROUPS = DISPLAY_SUBGROUPS["klaviyo"]

# Shopify does not report value/orders for free-shipping codes. Keep aliases so
# daily-file rows still roll into group totals, but never emit a display row.
OMIT_SUBGROUPS: Dict[str, List[Tuple[str, str, Tuple[str, ...], bool]]] = {
    "klaviyo": [
        (
            "free_shipping",
            "Abandoned checkout / free shipping",
            ("Abandoned checkout / free shipping (FS-)", "Abandoned checkout / free shipping"),
            True,
        ),
    ],
}
OMIT_SUBGROUP_IDS = frozenset(sid for rows in OMIT_SUBGROUPS.values() for sid, *_ in rows)


def _omitted_sub(gid: str, sid: str, label: str, free: bool) -> bool:
    if sid in OMIT_SUBGROUP_IDS or free:
        return True
    if any(sid == hid for hid, *_ in OMIT_SUBGROUPS.get(gid, [])):
        return True
    lower = (label or "").lower()
    return "abandoned checkout" in lower or "free shipping" in lower


def _bundled_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "discount_types"


_COVERAGE_END_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})")


def _coverage_end(path: Path) -> str:
    match = _COVERAGE_END_RE.search(path.name)
    return match.group(2) if match else ""


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def discount_types_dirs(data_root: Path) -> List[Path]:
    """Bundled snapshot, plus any uploaded history under the data root.

    Uploads land in ``data/discount_types`` or a week slot
    (``raw/{week}/discount_types`` or ``raw/{week}/discounts``).
    """
    root = Path(data_root)
    candidates = [
        _bundled_dir(),
        root / "discount_types",
        root / "weekly_report" / "data" / "discount_types",
    ]
    raw = root / "raw"
    if raw.is_dir():
        for week_dir in raw.iterdir():
            if not week_dir.is_dir():
                continue
            candidates.append(week_dir / "discount_types")
            candidates.append(week_dir / "discounts")
    seen: List[Path] = []
    for d in candidates:
        try:
            resolved = d.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.append(resolved)
    return seen


def _matching_paths(folders: Sequence[Path], prefix: str) -> List[Path]:
    """Every CSV for this prefix, lowest priority first.

    The bundled history stays. An uploaded week file wins on the days it
    contains, even when a deploy has made the bundled file look newer.
    A later end date beats an earlier one, then a newer upload.
    """
    bundled = _bundled_dir()
    found: Dict[str, Path] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.glob(f"{prefix}*.csv"):
            try:
                key = str(path.resolve())
            except OSError:
                key = str(path)
            found[key] = path
    paths = list(found.values())
    paths.sort(
        key=lambda path: (
            not _is_under(path, bundled),
            _coverage_end(path),
            _mtime(path),
            path.name,
        )
    )
    return paths


def _merge_by_day(paths: Sequence[Path], date_col: str) -> Tuple[pd.DataFrame, List[str]]:
    """Stack every file. A day that appears again is taken from the later file only."""
    frames: List[pd.DataFrame] = []
    used: List[str] = []
    for rank, path in enumerate(paths):
        frame = _read_csv(path)
        if frame.empty or date_col not in frame.columns:
            continue
        frame = frame.copy()
        frame["_day"] = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize()
        frame = frame.dropna(subset=["_day"])
        if frame.empty:
            continue
        frame["_rank"] = rank
        frames.append(frame)
        used.append(path.name)
    if not frames:
        return pd.DataFrame(), []
    combined = pd.concat(frames, ignore_index=True)
    winning_rank = combined.groupby("_day")["_rank"].transform("max")
    kept = combined.loc[combined["_rank"].eq(winning_rank)].drop(columns=["_day", "_rank"])
    return kept.reset_index(drop=True), used


def _read_csv(path: Path) -> pd.DataFrame:
    from weekly_report.src.metrics.discounts_sales import _read_csv_flexible

    df = _read_csv_flexible(path)
    df.columns = [str(c).strip().replace('"', "") for c in df.columns]
    return df


def apply_code_mapping(daily: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Mapping wins over the daily file's group/subgroup on code_or_title match."""
    if daily.empty or mapping is None or mapping.empty:
        return daily
    m = mapping.copy()
    if "code_or_title" not in m.columns or "group" not in m.columns:
        return daily
    m["code_or_title"] = m["code_or_title"].astype(str).str.strip()
    m = m.drop_duplicates("code_or_title", keep="first")
    idx = m.set_index("code_or_title")
    out = daily.copy()
    key = out["code_or_title"].astype(str).str.strip()
    mapped_group = key.map(idx["group"])
    if "subgroup" in idx.columns:
        mapped_sub = key.map(idx["subgroup"])
        out.loc[mapped_sub.notna(), "subgroup"] = mapped_sub[mapped_sub.notna()]
    out.loc[mapped_group.notna(), "group"] = mapped_group[mapped_group.notna()]
    return out


def _canonical_group_id(raw: str) -> str:
    text = str(raw or "").strip()
    for gid, _label, aliases in DISPLAY_GROUPS:
        if text in aliases:
            return gid
        stripped = text.lstrip("0123456789 ").strip()
        if stripped in aliases or text == _label:
            return gid
    return "other"


def _klaviyo_subgroup_id(raw: str) -> Optional[str]:
    text = str(raw or "").strip()
    for sid, _label, aliases, _free in (*KLAVIYO_SUBGROUPS, *OMIT_SUBGROUPS.get("klaviyo", [])):
        if text in aliases:
            return sid
    lower = text.lower()
    if "welcome" in lower:
        return "welcome_code"
    if "memor" in lower:
        return "memories"
    if "winback" in lower:
        return "inactive_winback"
    if "free shipping" in lower or lower.startswith("fs-") or "abandoned" in lower:
        return "free_shipping"
    return None


def _slug_sub_id(raw: str) -> str:
    text = str(raw or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return slug or "unspecified"


def _raw_subgroup(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("", "nan", "none") else text


def _resolve_sub(gid: str, raw: Any) -> Tuple[str, str, bool]:
    """Return (id, display label, is_free_shipping) for a raw subgroup string."""
    text = _raw_subgroup(raw)
    catalog = list(DISPLAY_SUBGROUPS.get(gid, [])) + list(OMIT_SUBGROUPS.get(gid, []))
    for sid, label, aliases, free in catalog:
        if text in aliases or text == label:
            return sid, label, free
    if gid == "klaviyo":
        fuzzy = _klaviyo_subgroup_id(text)
        if fuzzy:
            for sid, label, _aliases, free in catalog:
                if sid == fuzzy:
                    return sid, label, free
    return _slug_sub_id(text), text or "Unspecified", False


def _empty_subgroups(gid: str, gross: float) -> List[Dict[str, Any]]:
    return [
        {
            "id": sid,
            "label": slabel,
            **_metrics(0.0, 0.0, 0.0, gross, free_shipping=free),
        }
        for sid, slabel, _a, free in DISPLAY_SUBGROUPS.get(gid, [])
        if not _omitted_sub(gid, sid, slabel, free)
    ]


def _group_subgroups(
    gid: str,
    dsub: pd.DataFrame,
    amount_col: str,
    orders_col: str,
    total_disc: float,
    gross: float,
) -> List[Dict[str, Any]]:
    """Curated subgroups first (always listed), then any extra names in this window."""
    gslice = dsub[dsub["_group_id"] == gid] if (dsub is not None and not dsub.empty) else pd.DataFrame()
    meta: Dict[str, Tuple[str, bool]] = {}
    amounts: Dict[str, float] = {}
    orders: Dict[str, float] = {}
    if not gslice.empty:
        for _, row in gslice.iterrows():
            sid, label, free = _resolve_sub(gid, row["subgroup"] if "subgroup" in gslice.columns else "")
            meta.setdefault(sid, (label, free))
            amt = pd.to_numeric(row.get(amount_col, 0.0), errors="coerce")
            ords = pd.to_numeric(row.get(orders_col, 0.0), errors="coerce")
            amounts[sid] = amounts.get(sid, 0.0) + (0.0 if pd.isna(amt) else float(amt))
            orders[sid] = orders.get(sid, 0.0) + (0.0 if pd.isna(ords) else float(ords))

    seen: set = set()
    out: List[Dict[str, Any]] = []
    for sid, _slabel, _a, _free in OMIT_SUBGROUPS.get(gid, []):
        seen.add(sid)
    for sid, slabel, _a, free in DISPLAY_SUBGROUPS.get(gid, []):
        seen.add(sid)
        if _omitted_sub(gid, sid, slabel, free):
            continue
        out.append(
            {
                "id": sid,
                "label": slabel,
                **_metrics(amounts.get(sid, 0.0), orders.get(sid, 0.0), total_disc, gross, free_shipping=free),
            }
        )
    extras = [sid for sid in amounts if sid not in seen]
    extras.sort(key=lambda sid: meta.get(sid, (sid, False))[0].lower())
    for sid in extras:
        label, free = meta.get(sid, (sid, False))
        if _omitted_sub(gid, sid, label, free):
            continue
        out.append(
            {
                "id": sid,
                "label": label,
                **_metrics(amounts.get(sid, 0.0), orders.get(sid, 0.0), total_disc, gross, free_shipping=free),
            }
        )
    return out


def load_discount_type_tables(data_root: Path) -> Dict[str, Any]:
    folders = discount_types_dirs(data_root)
    daily, group_files = _merge_by_day(_matching_paths(folders, "discount_groups_daily_"), "date")
    totals, total_files = _merge_by_day(_matching_paths(folders, "shopify_daily_totals_"), "date")
    mapping_path = None
    for folder in folders:
        candidate = folder / "discount_code_mapping.csv"
        if candidate.exists():
            mapping_path = candidate
            break

    files_used: List[str] = [*group_files, *total_files]
    mapping = pd.DataFrame()
    if mapping_path is not None:
        mapping = _read_csv(mapping_path)
        files_used.append(mapping_path.name)
        if not daily.empty:
            daily = apply_code_mapping(daily, mapping)

    return {
        "daily": daily,
        "totals": totals,
        "mapping": mapping,
        "files_used": files_used,
        "folders": [str(f) for f in folders],
    }


def _prepare_money(df: pd.DataFrame, date_col: str, money_cols: List[str], data_root: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame(), {"applied": False}
    out = df.copy()
    out["_date"] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=["_date"])
    out["_date"] = out["_date"].dt.normalize()
    extra = []
    for col in money_cols:
        if col not in out.columns:
            out[col] = 0.0
        internal = f"_{col}"
        out[internal] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        extra.append(internal)
    if "orders" in out.columns:
        out["_orders"] = pd.to_numeric(out["orders"], errors="coerce").fillna(0.0)
    converted, fx = convert_revenue_over_time_to_sek(out, Path(data_root), extra_money_cols=extra)
    return converted, fx


def _metrics(amount: float, orders: float, total_disc: float, gross: float, *, free_shipping: bool = False) -> Dict[str, Any]:
    shown = 0.0 if free_shipping else float(amount or 0.0)
    share = (shown / total_disc * 100.0) if total_disc > 0 and not free_shipping else (0.0 if total_disc > 0 else None)
    pct_gross = (shown / gross * 100.0) if gross > 0 else None
    if free_shipping:
        pct_gross = 0.0 if gross > 0 else None
        share = 0.0 if total_disc > 0 else None
    return {
        "discount_amount": shown,
        "orders": int(round(float(orders or 0.0))),
        "share_of_discounts_pct": share,
        "pct_of_gross_sales": pct_gross,
        "is_free_shipping": free_shipping,
    }


def _window_slice(daily: pd.DataFrame, totals: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> Dict[str, Any]:
    dsub = daily[(daily["_date"] >= start) & (daily["_date"] <= end)] if not daily.empty else daily
    tsub = totals[(totals["_date"] >= start) & (totals["_date"] <= end)] if not totals.empty else totals
    gross = float(tsub["_gross_sales_usd"].sum()) if (not tsub.empty and "_gross_sales_usd" in tsub.columns) else 0.0
    shopify_disc = (
        float(tsub["_discount_amount_usd"].sum()) if (not tsub.empty and "_discount_amount_usd" in tsub.columns) else 0.0
    )
    shopify_orders = float(tsub["_orders"].sum()) if (not tsub.empty and "_orders" in tsub.columns) else 0.0

    if dsub is None or dsub.empty:
        total_disc = 0.0
        groups_out: List[Dict[str, Any]] = []
        for gid, label, _aliases in DISPLAY_GROUPS:
            groups_out.append(
                {
                    "id": gid,
                    "label": label,
                    **_metrics(0.0, 0.0, 0.0, gross, free_shipping=False),
                    "subgroups": _empty_subgroups(gid, gross),
                }
            )
        return {
            "gross_sales": gross,
            "discount_amount": 0.0,
            "shopify_discount_amount": shopify_disc,
            "orders": 0,
            "shopify_orders": int(round(shopify_orders)),
            "discount_of_gross_pct": None,
            "groups": groups_out,
        }

    dsub = dsub.copy()
    dsub["_group_id"] = dsub["group"].map(_canonical_group_id)
    amount_col = "_discount_amount_usd" if "_discount_amount_usd" in dsub.columns else "discount_amount_usd"
    orders_col = "_orders" if "_orders" in dsub.columns else "orders"
    total_disc = float(pd.to_numeric(dsub[amount_col], errors="coerce").fillna(0.0).sum())

    grouped = dsub.groupby("_group_id", dropna=False)[[amount_col, orders_col]].sum()

    groups_out = []
    for gid, label, _aliases in DISPLAY_GROUPS:
        if gid in grouped.index:
            amt = float(grouped.loc[gid, amount_col] or 0.0)
            ords = float(grouped.loc[gid, orders_col] or 0.0)
        else:
            amt = 0.0
            ords = 0.0
        groups_out.append(
            {
                "id": gid,
                "label": label,
                **_metrics(amt, ords, total_disc, gross, free_shipping=False),
                "subgroups": _group_subgroups(gid, dsub, amount_col, orders_col, total_disc, gross),
            }
        )

    disc_of_gross = (total_disc / gross * 100.0) if gross > 0 else None
    return {
        "gross_sales": gross,
        "discount_amount": total_disc,
        "shopify_discount_amount": shopify_disc,
        "orders": int(round(float(pd.to_numeric(dsub[orders_col], errors="coerce").fillna(0.0).sum()))),
        "shopify_orders": int(round(shopify_orders)),
        "discount_of_gross_pct": disc_of_gross,
        "groups": groups_out,
    }


def _yoy_block(cur: Dict[str, Any], ly: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **{k: cur[k] for k in ("gross_sales", "discount_amount", "orders", "discount_of_gross_pct", "groups", "shopify_discount_amount", "shopify_orders") if k in cur},
        "last_year": {
            k: ly[k]
            for k in ("gross_sales", "discount_amount", "orders", "discount_of_gross_pct", "groups", "shopify_discount_amount", "shopify_orders")
            if k in ly
        },
    }


def calculate_discount_types(
    base_week: str,
    data_root: Path,
    *,
    granularity: str = "week",
    num_weeks: int = 8,
    months: int = 13,
) -> Dict[str, Any]:
    tables = load_discount_type_tables(data_root)
    daily_raw = tables["daily"]
    totals_raw = tables["totals"]

    daily, fx = _prepare_money(
        daily_raw,
        "date",
        ["discount_amount_usd", "gross_sales_usd"],
        data_root,
    )
    totals, fx_tot = _prepare_money(
        totals_raw,
        "date",
        ["gross_sales_usd", "discount_amount_usd"],
        data_root,
    )

    fx = fx if fx.get("applied") else fx_tot
    currency = fx.get("target_currency", "SEK") if fx.get("applied") else "USD"

    base: Dict[str, Any] = {
        "base_week": base_week,
        "granularity": granularity,
        "num_weeks": num_weeks,
        "months": months,
        "source": "discount_types",
        "note": NOTE,
        "files_used": tables["files_used"],
        "currency": currency,
        "fx": fx,
        "periods": [],
    }
    if daily.empty and totals.empty:
        return {**base, "error": "no_discount_type_files"}

    if not daily.empty:
        daily["_week"] = _iso_week_series(daily["_date"])
    if not totals.empty:
        totals["_week"] = _iso_week_series(totals["_date"])

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {**base, "error": "Invalid base_week date range"}

    periods_out: List[Dict[str, Any]] = []
    if granularity == "month":
        end_period = week_end.to_period("M")
        count = max(1, int(months or 13))
        month_keys = [(end_period - i) for i in range(count)]
        for mp in month_keys:
            is_latest = mp == end_period
            start = mp.start_time.normalize()
            end = week_end.normalize() if is_latest else mp.end_time.normalize()
            ly_p = mp - 12
            ly_end = (week_end - pd.DateOffset(years=1)) if is_latest else ly_p.end_time.normalize()
            cur = _window_slice(daily, totals, start, end)
            ly = _window_slice(daily, totals, ly_p.start_time.normalize(), ly_end)
            periods_out.append(
                {
                    "key": mp.strftime("%Y-%m"),
                    "month": mp.strftime("%Y-%m"),
                    "start": str(start.date()),
                    "end": str(end.date()),
                    **_yoy_block(cur, ly),
                }
            )
    else:
        expected = _build_display_weeks(base_week, num_weeks)
        for w in expected:
            rng = get_week_date_range(w)
            start = pd.Timestamp(rng["start"]).normalize()
            end = pd.Timestamp(rng["end"]).normalize()
            y_str, ww = w.split("-")
            ly_w = f"{int(y_str) - 1}-{ww}"
            ly_rng = get_week_date_range(ly_w)
            cur = _window_slice(daily, totals, start, end)
            ly = _window_slice(
                daily,
                totals,
                pd.Timestamp(ly_rng["start"]).normalize(),
                pd.Timestamp(ly_rng["end"]).normalize(),
            )
            periods_out.append(
                {
                    "key": w,
                    "week": w,
                    "start": str(start.date()),
                    "end": str(end.date()),
                    **_yoy_block(cur, ly),
                }
            )

    hist_start = hist_end = None
    if not daily.empty:
        hist_start = str(daily["_date"].min().date())
        hist_end = str(daily["_date"].max().date())
    elif not totals.empty:
        hist_start = str(totals["_date"].min().date())
        hist_end = str(totals["_date"].max().date())

    return {
        **base,
        "history_range": {"start": hist_start, "end": hist_end} if hist_start else None,
        "periods": periods_out,
    }
