"""Budget and actuals compute: same shape as /api/budget-general and /api/actuals-* for sync and routes."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
from loguru import logger

from weekly_report.src.config import load_config


def _parse_number(value: Any) -> float:
    """Robust number parser for budget values with locale artifacts."""
    try:
        if pd.isna(value):
            return float('nan')
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if s == '':
            return float('nan')
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]
        s = s.replace(' ', '').replace('%', '')
        if ',' in s and '.' in s:
            s = s.replace(',', '')
        elif ',' in s and '.' not in s:
            parts = s.split(',')
            if all(len(p) == 3 for p in parts[1:]):
                s = ''.join(parts)
            else:
                s = s.replace(',', '.')
        return float(s)
    except Exception:
        return float('nan')


def _fetch_budget_dataframe(week: str):
    """Load budget CSV as a single combined DataFrame (same resolution as budget-general)."""
    config = load_config(week=week)
    from weekly_report.src.adapters.budget import load_data

    df = None
    try:
        df = load_data(config.raw_data_path, base_week=week)
    except FileNotFoundError:
        pass
    if df is None or df.empty:
        year = int(week.split("-")[0])
        raw_dir = config.data_root / "raw"
        if raw_dir.exists():
            for p in sorted(raw_dir.iterdir(), reverse=True):
                if p.is_dir() and p.name.startswith(str(year) + "-"):
                    try:
                        df = load_data(p, base_week=p.name)
                        if df is not None and not df.empty:
                            logger.info(f"Using budget from week folder {p.name} for {week}")
                            break
                    except FileNotFoundError:
                        continue
    if df is None or df.empty:
        try:
            df = load_data(config.data_root / "raw", base_week=week)
        except FileNotFoundError:
            return None
    if df is None or df.empty:
        return None
    return df


def compute_budget_general(week: str) -> Dict[str, Any]:
    """
    Aggregate budget metrics across all markets by Month.
    Same shape as /api/budget-general for map_budget_general_to_rows.
    Returns {"error": "..."} on failure so sync can skip and continue.
    """
    try:
        df = _fetch_budget_dataframe(week)
        if df is None:
            return {"error": "Budget file not found. Upload in Settings (week folder or data/raw/budget)."}

        # Strip BOM and whitespace from column names
        df.columns = df.columns.str.replace("\ufeff", "").str.strip()
        # Drop source columns for processing
        df_work = df.drop(columns=[c for c in df.columns if c in {"_source_file", "_source_type", "_source_location"}], errors="ignore")

        def _parse_month_col(c: str):
            s = str(c).strip().replace("\ufeff", "")
            if not s:
                return None
            try:
                dt = datetime.strptime(s, "%B %Y")
                return dt, s
            except Exception:
                pass
            try:
                dt = datetime.strptime(s, "%b %Y")
                return dt, s
            except Exception:
                pass
            try:
                dt = datetime.strptime(s[:7], "%Y-%m")
                return dt, s
            except Exception:
                pass
            return None

        # Detect "months as columns" layout: no Month column but columns that look like "March 2026"
        month_cols = []
        for c in df_work.columns:
            parsed = _parse_month_col(c)
            if parsed is not None:
                month_cols.append((parsed[0], parsed[1]))
        months_as_columns = "Month" not in df_work.columns and len(month_cols) > 0
        if months_as_columns:
            month_cols.sort(key=lambda x: x[0])
            months_order = [m[1] for m in month_cols]
            key_col = df_work.columns[0]
            table = {}
            for _, row in df_work.iterrows():
                label = str(row.get(key_col, "")).strip()
                if not label:
                    continue
                by_month = {}
                for _dt, month_name in month_cols:
                    val = row.get(month_name)
                    if val is not None and month_name in row.index:
                        v = _parse_number(val)
                        if not (pd.isna(v) or v == float("inf") or v == float("-inf")):
                            by_month[month_name] = float(v)
                if by_month:
                    table[label] = by_month
            month_parsed = {m[1]: m[0] for m in month_cols}
            now = datetime.now()
            totals = {k: sum(v.values()) for k, v in table.items()}
            ytd_totals = {}
            for metric, by_month in table.items():
                ytd_val = 0.0
                for m, v in by_month.items():
                    mp = month_parsed.get(m)
                    if mp is not None and (mp.year < now.year or (mp.year == now.year and mp.month <= now.month)):
                        ytd_val += v
                ytd_totals[metric] = ytd_val
            return {
                "week": week,
                "months": months_order,
                "metrics": list(table.keys()),
                "table": table,
                "totals": totals,
                "ytd_totals": ytd_totals,
                "customer_by_metric": {},
                "display_name_by_metric": {},
            }

        if "Month" in df_work.columns:
            df_work["Month"] = df_work["Month"].astype(str).str.strip()
        if "Market" in df_work.columns:
            df_work["Market"] = df_work["Market"].astype(str).str.strip()

        if "Market" in df_work.columns:
            total_aliases = {"total", "all", "all markets", "grand total", "totals"}
            df_work = df_work[~df_work["Market"].str.lower().isin(total_aliases)]
            df_work = df_work[df_work["Market"].str.len() > 0]

        dimension_cols = {"Month", "Market", "_source_file", "_source_type"}
        existing_dimension_cols = [c for c in df_work.columns if c in dimension_cols]
        value_df = df_work.drop(columns=[c for c in existing_dimension_cols if c in df_work.columns], errors="ignore").copy()
        for col in value_df.columns:
            value_df[col] = value_df[col].map(_parse_number)
        numeric_df = value_df

        def derive_gross(d: pd.DataFrame, net_col: str, returns_col: str, gross_col: str) -> None:
            if net_col in d.columns and returns_col in d.columns:
                try:
                    d[gross_col] = d[net_col] - d[returns_col]
                except Exception:
                    pass
        derive_gross(numeric_df, "Returning Net Revenue", "Returning Returns", "Returning Gross Revenue")
        derive_gross(numeric_df, "New Net Revenue", "New Returns", "New Gross Revenue")

        if "Month" not in df_work.columns:
            return {"error": "Budget file missing 'Month' column"}

        df = df_work

        df_grouped = pd.concat([df[["Month"]], numeric_df], axis=1).groupby("Month", as_index=False).sum(numeric_only=True)
        try:
            df_grouped["__month_dt"] = pd.to_datetime(df_grouped["Month"], format="%B %Y", errors="coerce")
        except Exception:
            df_grouped["__month_dt"] = pd.to_datetime(df_grouped["Month"], errors="coerce")
        df_grouped = df_grouped.sort_values(["__month_dt", "Month"], ascending=[True, True]).drop(columns=["__month_dt"])
        months_order = df_grouped["Month"].tolist()

        now = datetime.now()
        def parse_month_str(m: str):
            try:
                return datetime.strptime(m, "%B %Y")
            except Exception:
                try:
                    return datetime.fromisoformat(m)
                except Exception:
                    return None
        month_parsed = {m: parse_month_str(m) for m in months_order}

        whitelist = [
            'Returning Customers', 'Share of Returning Customers', 'Returning Gross Revenue', 'Returning Returns',
            'Returning Net Revenue', 'Returning Cost of Goods Sold', 'Returning Orders', 'Returning Order Frequency',
            'Returning AOV', 'Returning Revenue per Customer',
            'New Customers', 'Share of New Customers', 'New Gross Revenue', 'New Returns', 'New Net Revenue',
            'New Cost of Goods Sold', 'New Orders', 'New Order Frequency', 'New AOV', 'New Revenue per Customer',
            'Total Customers', 'Total Orders', 'Total AOV', 'Revenue per Customer', 'Order Frequency', 'Total Gross Revenue',
            'Online Marketing Spend', 'COS %', 'aMER',
        ]
        all_numeric_cols = [c for c in df_grouped.columns if c != "Month"]
        # Case-insensitive match: map whitelist name to actual CSV column name so "Online marketing spend" etc. work
        col_lower_to_actual = {c.strip().lower(): c for c in all_numeric_cols}
        metric_cols = [w for w in whitelist if w.lower() in col_lower_to_actual]
        col_for_metric = {w: col_lower_to_actual[w.lower()] for w in metric_cols}
        desired_order = [
            "Returning Customers", "Share of Returning Customers", "Returning Gross Revenue", "Returning Returns",
            "Returning Net Revenue", "Returning Cost of Goods Sold", "Returning Orders", "Returning Order Frequency",
            "Returning AOV", "Returning Revenue per Customer",
            "New Customers", "Share of New Customers", "New Gross Revenue", "New Returns", "New Net Revenue",
            "New Cost of Goods Sold", "New Orders", "New Order Frequency", "New AOV", "New Revenue per Customer",
        ]
        priority_index = {name.lower(): i for i, name in enumerate(desired_order)}
        def metric_key(name: str):
            idx = priority_index.get(name.lower())
            return (0, idx) if idx is not None else (1, name.lower())
        metric_cols = sorted(metric_cols, key=metric_key)

        table = {}
        totals = {}
        ytd_totals = {}
        customer_by_metric = {}
        display_name_by_metric = {}
        for metric in metric_cols:
            metric_lower = metric.lower()
            if metric_lower.startswith('new '):
                customer_by_metric[metric] = 'New'
            elif metric_lower.startswith('returning '):
                customer_by_metric[metric] = 'Returning'
            else:
                customer_by_metric[metric] = ''
            if metric_lower.startswith('share of returning customers'):
                display_name_by_metric[metric] = 'Share of total %'
                customer_by_metric[metric] = 'Returning'
            elif metric_lower.startswith('share of new customers'):
                display_name_by_metric[metric] = 'Share of total %'
                customer_by_metric[metric] = 'New'
            else:
                display_name_by_metric[metric] = metric
            by_month = {}
            total_val = 0.0
            read_col = col_for_metric.get(metric, metric)
            for _, row in df_grouped.iterrows():
                m = row["Month"]
                val = float(row[read_col]) if pd.notna(row.get(read_col)) else 0.0
                if val == float('inf') or val == float('-inf'):
                    val = 0.0
                by_month[m] = val
                total_val += val
            table[metric] = by_month
            totals[metric] = total_val
            ytd_val = 0.0
            for m, v in by_month.items():
                mp = month_parsed.get(m)
                if mp is not None and (mp.year < now.year or (mp.year == now.year and mp.month <= now.month)):
                    ytd_val += v
            ytd_totals[metric] = ytd_val

        return {
            "week": week,
            "months": months_order,
            "metrics": metric_cols,
            "table": table,
            "totals": totals,
            "ytd_totals": ytd_totals,
            "customer_by_metric": customer_by_metric,
            "display_name_by_metric": display_name_by_metric,
        }
    except Exception as e:
        logger.warning(f"compute_budget_general failed: {e}")
        return {"error": str(e)}


def _normalize_market_geography_column(df: pd.DataFrame) -> pd.DataFrame:
    """Budget files may use Country, Land, Marknad, or market instead of Market."""
    out = df.copy()
    lower = {str(c).strip().lower(): c for c in out.columns}
    if "market" in lower and "Market" not in out.columns:
        out = out.rename(columns={lower["market"]: "Market"})
    if "Market" in out.columns:
        return out
    for alt in ("Country", "Land", "Marknad", "Market name", "Geography", "Region"):
        key = alt.lower()
        if key in lower:
            return out.rename(columns={lower[key]: "Market"})
    return out


def _is_row_dimension_budget_label(name: str) -> bool:
    """ROW / Rest of World is a real budget bucket — never strip it as an aggregate."""
    s = str(name).strip().lower()
    if s in ("row", "r.o.w.", "others", "other", "other markets", "rom"):
        return True
    return "rest of world" in s


def _strip_aggregate_market_rows(by_market: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Remove Total CDLP / group totals so we only keep country-like markets (else Qlik countries never match)."""
    agg_substrings = (
        "grand total",
        "all markets",
        "total cdlp",
        "cdlp total",
        "group total",
        "company total",
        "online total",
    )
    fixed = {
        "total",
        "all",
        "totals",
        "cdlp",
        "group",
    }
    cleaned: Dict[str, Dict[str, float]] = {}
    for k, v in by_market.items():
        if _is_row_dimension_budget_label(k):
            cleaned[k] = v
            continue
        s = str(k).strip().lower()
        if not s or s in fixed:
            continue
        if any(t in s for t in agg_substrings):
            continue
        if s.startswith("total ") and len(s) < 45:
            continue
        cleaned[k] = v
    return cleaned


def _metric_label_is_net_revenue_budget(label: str) -> bool:
    """True if this row/cell describes online / total net revenue (not gross) in budget files."""
    raw = str(label).strip().lower()
    s = "".join(c for c in raw if c.isalnum())
    if not s:
        return False
    if "gross" in s or "brutto" in s:
        return False
    if s in ("netrevenue", "onlinenetrevenue", "totalnetrevenue", "onlinenetsales"):
        return True
    if "netrevenue" in s or "nettorevenue" in s:
        return True
    if "netsales" in s or "netsale" in s or "nettooms" in s or "netoms" in s:
        return True
    if "onlinenet" in s or ("ecommerce" in s and "net" in s):
        return True
    if raw == "net revenue" or s == "netrevenue":
        return True
    if "returningnetrevenue" in s or "newnetrevenue" in s:
        return True
    return False


def _normalize_month_label_for_lookup(mon: Any) -> str:
    """Store months canonically as 'March 2026' so week/MTD lookups match."""
    ts = pd.to_datetime(mon, errors="coerce")
    if pd.notna(ts):
        return ts.strftime("%B %Y")
    return str(mon).strip()


def _budget_lower_col_map(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).strip().lower(): c for c in df.columns}


def _pick_budget_col(cmap: Dict[str, str], *names: str) -> Optional[str]:
    for n in names:
        k = n.strip().lower()
        if k in cmap:
            return cmap[k]
    return None


def _month_year_to_canonical(month_part: Any, year_part: Any) -> Optional[str]:
    """Combine Month='April' + Year=2026 → 'April 2026' (skips fiscal labels like 2025/26)."""
    if month_part is None or (isinstance(month_part, float) and pd.isna(month_part)):
        return None
    mo_str = str(month_part).strip()
    if not mo_str or mo_str.lower() in ("nan", "none", "nat"):
        return None
    if year_part is None or (isinstance(year_part, float) and pd.isna(year_part)):
        return None
    yr_raw = str(year_part).strip()
    if not yr_raw or yr_raw.lower() in ("nan", "none"):
        return None
    if "/" in yr_raw.replace(" ", ""):
        return None
    try:
        y = int(float(yr_raw))
    except (TypeError, ValueError):
        return None
    ts = pd.to_datetime(f"{mo_str} {y}", errors="coerce")
    if pd.notna(ts):
        return ts.strftime("%B %Y")
    for fmt in ("%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(f"{mo_str} {y}", fmt)
            return dt.strftime("%B %Y")
        except Exception:
            continue
    return None


def _budget_scenario_rank(scen_raw: Any) -> Optional[int]:
    """
    Prefer BUDGET over ESTIMATE over FORECAST over PLAN when the same market+month appears
    under multiple scenarios (e.g. ESTIMATE for Feb–Mar, BUDGET from fiscal April onward).
    Returns None to skip the row (actuals / totals).
    """
    if scen_raw is None or (isinstance(scen_raw, float) and pd.isna(scen_raw)):
        return 0
    s = str(scen_raw).strip().upper()
    if not s or s == "NAN":
        return 0
    if s in ("ACTUAL", "ACTUALS", "ACT", "TOTAL", "TOTALS", "A"):
        return None
    order = {
        "BUDGET": 0,
        "ESTIMATE": 1,
        "FORECAST": 2,
        "PLAN": 3,
        "PLANNING": 3,
        "PROJECTION": 2,
    }
    return order.get(s, 4)


def _infer_budget_value_column(df: pd.DataFrame, exclude: List[Any]) -> Optional[str]:
    """Pick the column that is mostly numeric when Value/Amount header is missing or odd."""
    excl = {x for x in exclude if x is not None}
    best: Optional[str] = None
    best_ratio = 0.0
    for c in df.columns:
        if c in excl:
            continue
        if str(c).startswith("_"):
            continue
        ser = pd.to_numeric(df[c], errors="coerce")
        ratio = float(ser.notna().sum()) / max(len(df), 1)
        if ratio > best_ratio and ratio >= 0.25:
            best_ratio = ratio
            best = c
    return best


def _row_net_budget_from_numeric(row: pd.Series) -> float:
    """One row of metric columns: prefer Net Revenue; else Returning + New net."""
    cmap = {str(c).strip().lower(): c for c in row.index}
    if "net revenue" in cmap:
        v = row[cmap["net revenue"]]
        if pd.notna(v) and v == v:
            return float(v)
    total = 0.0
    for key in ("returning net revenue", "new net revenue"):
        if key in cmap:
            v = row[cmap[key]]
            if pd.notna(v) and v == v:
                total += float(v)
    return total


def compute_budget_net_by_market_month(week: str) -> Dict[str, Any]:
    """
    Online net budget per Market and Month label (as in CSV), for top-markets MTD.
    Returns {"by_market": {market: {month_str: float}}, "error": optional}.
    """
    try:
        df = _fetch_budget_dataframe(week)
        if df is None:
            return {"by_market": {}, "error": "Budget file not found"}
        df.columns = df.columns.str.replace("\ufeff", "").str.strip()
        df_work = df.drop(
            columns=[c for c in df.columns if c in {"_source_file", "_source_type", "_source_location"}],
            errors="ignore",
        )
        df_work = _normalize_market_geography_column(df_work)

        total_aliases = {"total", "all", "all markets", "grand total", "totals"}
        by_market: Dict[str, Dict[str, float]] = {}

        # Long: Market + Metric + Month [+ Year] + Value (+ Type/Scenario = BUDGET / ESTIMATE / …)
        cmap_bm = _budget_lower_col_map(df_work)
        col_market = _pick_budget_col(cmap_bm, "market", "country", "land", "marknad")
        col_metric = _pick_budget_col(
            cmap_bm, "metric", "measure", "kpi", "net revenue", "revenue metric"
        )
        col_value = _pick_budget_col(
            cmap_bm, "value", "amount", "budget", "values", "data", "sek", "tcy", "fy budget"
        )
        col_month = _pick_budget_col(cmap_bm, "month", "mon", "period month", "month name")
        col_year = _pick_budget_col(cmap_bm, "year", "yr", "fiscal year", "fiscalyear")
        col_type = _pick_budget_col(cmap_bm, "type", "scenario", "version", "source")

        excl_infer = [c for c in (col_market, col_metric, col_month, col_year, col_type) if c]
        if col_market and col_metric and col_month and not col_value:
            col_value = _infer_budget_value_column(df_work, excl_infer)

        if col_market and col_metric and col_value and col_month:
            sub = df_work.copy()
            sub[col_market] = sub[col_market].astype(str).str.strip()
            sub = sub[~sub[col_market].str.lower().isin(total_aliases)]

            cell_parts: Dict[Tuple[str, str], List[Tuple[int, float]]] = defaultdict(list)
            for _, r in sub.iterrows():
                if not _metric_label_is_net_revenue_budget(r.get(col_metric, "")):
                    continue
                mkt = str(r[col_market]).strip()
                if not mkt:
                    continue
                mon_raw = r.get(col_month)
                if mon_raw is None or (isinstance(mon_raw, float) and pd.isna(mon_raw)):
                    continue
                if str(mon_raw).strip() == "":
                    continue

                mon_n: Optional[str] = None
                if col_year is not None and col_year in sub.columns:
                    yv = r.get(col_year)
                    if yv is not None and str(yv).strip() != "" and pd.notna(yv):
                        mon_n = _month_year_to_canonical(mon_raw, yv)
                if not mon_n:
                    mon_n = _normalize_month_label_for_lookup(mon_raw)
                if not mon_n:
                    continue
                if pd.isna(pd.to_datetime(mon_n, errors="coerce")):
                    continue

                if col_type and col_type in sub.columns:
                    rk = _budget_scenario_rank(r.get(col_type))
                    if rk is None:
                        continue
                else:
                    rk = 0

                v = _parse_number(r.get(col_value))
                if pd.isna(v) or v in (float("inf"), float("-inf")):
                    continue
                cell_parts[(mkt, mon_n)].append((rk, float(v)))

            for (mkt, mon_n), parts in cell_parts.items():
                best = min(p[0] for p in parts)
                total_v = sum(p[1] for p in parts if p[0] == best)
                by_market.setdefault(mkt, {})
                by_market[mkt][mon_n] = total_v

            by_market = _strip_aggregate_market_rows(by_market)
            return {"by_market": by_market, "error": None}

        def _parse_month_col(c: str):
            s = str(c).strip().replace("\ufeff", "")
            if not s:
                return None
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return datetime.strptime(s, fmt), s
                except Exception:
                    continue
            try:
                return datetime.strptime(s[:7], "%Y-%m"), s
            except Exception:
                return None

        month_cols = []
        for c in df_work.columns:
            parsed = _parse_month_col(c)
            if parsed is not None:
                month_cols.append((parsed[0], parsed[1]))
        months_as_columns = "Month" not in df_work.columns and len(month_cols) > 0

        if months_as_columns and "Market" in df_work.columns:
            month_cols.sort(key=lambda x: x[0])
            month_name_set = {mn for _, mn in month_cols}
            label_candidates = [c for c in df_work.columns if c != "Market" and c not in month_name_set]
            if not label_candidates:
                return {"by_market": {}, "error": "wide_months_no_metric_column"}

            def _wide_ingest(strict_metric: bool) -> Dict[str, Dict[str, float]]:
                acc: Dict[str, Dict[str, float]] = {}
                for _, row in df_work.iterrows():
                    mkt = str(row.get("Market", "")).strip()
                    if not mkt or mkt.lower() in total_aliases:
                        continue
                    if strict_metric:
                        ok = any(
                            _metric_label_is_net_revenue_budget(str(row.get(lc, "")).strip())
                            for lc in label_candidates
                        )
                        if not ok:
                            continue
                    for _dt, mo_name in month_cols:
                        v = _parse_number(row.get(mo_name))
                        if pd.isna(v) or v in (float("inf"), float("-inf")):
                            continue
                        mo_key = _normalize_month_label_for_lookup(mo_name)
                        acc.setdefault(mkt, {})
                        acc[mkt][mo_key] = acc[mkt].get(mo_key, 0.0) + float(v)
                return acc

            by_market = _wide_ingest(True)
            if not by_market or not any(by_market.values()):
                mk = df_work["Market"].astype(str).str.strip()
                mk = mk[mk.str.len() > 0].str.lower()
                mk = mk[~mk.isin(total_aliases)]
                vc = mk.value_counts()
                one_row_per_market = vc.empty or int(vc.max()) == 1
                if one_row_per_market:
                    by_market = _wide_ingest(False)
                    if by_market:
                        logger.info(
                            "compute_budget_net_by_market_month: using implicit net rows (one row per market, wide months)"
                        )
                elif not by_market:
                    logger.warning(
                        "compute_budget_net_by_market_month: wide layout matched no net-revenue metric rows"
                    )

            by_market = _strip_aggregate_market_rows(by_market)
            return {"by_market": by_market, "error": None}

        if "Month" not in df_work.columns or "Market" not in df_work.columns:
            return {"by_market": {}, "error": "no_market_month_columns"}

        df_work["Month"] = df_work["Month"].astype(str).str.strip()
        df_work["Market"] = df_work["Market"].astype(str).str.strip()
        df_work = df_work[~df_work["Market"].str.lower().isin(total_aliases)]
        df_work = df_work[df_work["Market"].str.len() > 0]

        dimension_cols = {"Month", "Market", "_source_file", "_source_type"}
        existing_dimension_cols = [c for c in df_work.columns if c in dimension_cols]
        value_df = df_work.drop(columns=[c for c in existing_dimension_cols if c in df_work.columns], errors="ignore").copy()
        for col in value_df.columns:
            value_df[col] = value_df[col].map(_parse_number)

        def derive_gross(d: pd.DataFrame, net_col: str, returns_col: str, gross_col: str) -> None:
            if net_col in d.columns and returns_col in d.columns:
                try:
                    d[gross_col] = d[net_col] - d[returns_col]
                except Exception:
                    pass

        derive_gross(value_df, "Returning Net Revenue", "Returning Returns", "Returning Gross Revenue")
        derive_gross(value_df, "New Net Revenue", "New Returns", "New Gross Revenue")

        mm = df_work[["Market", "Month"]].reset_index(drop=True)
        num = value_df.reset_index(drop=True)
        nets = num.apply(_row_net_budget_from_numeric, axis=1)
        work = pd.concat([mm, nets.rename("__net")], axis=1)
        agg = work.groupby(["Market", "Month"], as_index=False)["__net"].sum()
        for _, r in agg.iterrows():
            mkt = str(r["Market"]).strip()
            mon = _normalize_month_label_for_lookup(r["Month"])
            v = float(r["__net"])
            by_market.setdefault(mkt, {})
            by_market[mkt][mon] = by_market[mkt].get(mon, 0.0) + v
        by_market = _strip_aggregate_market_rows(by_market)
        return {"by_market": by_market, "error": None}
    except Exception as e:
        logger.warning(f"compute_budget_net_by_market_month failed: {e}")
        return {"by_market": {}, "error": str(e)}


def compute_actuals_general(week: str) -> Dict[str, Any]:
    """Aggregate actuals across all markets by Month (same shape as budget-general). Not implemented yet."""
    return {"error": "Actuals general not implemented"}


def compute_actuals_markets_detailed(week: str) -> Dict[str, Any]:
    """Actuals per Market and Month. Not implemented yet."""
    return {"error": "Actuals markets detailed not implemented"}
