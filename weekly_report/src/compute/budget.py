"""Budget and actuals compute: same shape as /api/budget-general and /api/actuals-* for sync and routes."""

from typing import Any, Dict
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


def compute_budget_general(week: str) -> Dict[str, Any]:
    """
    Aggregate budget metrics across all markets by Month.
    Same shape as /api/budget-general for map_budget_general_to_rows.
    Returns {"error": "..."} on failure so sync can skip and continue.
    """
    try:
        config = load_config(week=week)
        from weekly_report.src.adapters.budget import load_data
        df = None
        try:
            df = load_data(config.raw_data_path, base_week=week)
        except FileNotFoundError:
            pass
        if df is None or df.empty:
            # Fallback 1: try any week folder for the same year (one upload can serve all weeks)
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
                return {"error": "Budget file not found. Upload in Settings (week folder or data/raw/budget)."}
        if df is None or df.empty:
            return {"error": "Budget file is empty"}

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


def compute_actuals_general(week: str) -> Dict[str, Any]:
    """Aggregate actuals across all markets by Month (same shape as budget-general). Not implemented yet."""
    return {"error": "Actuals general not implemented"}


def compute_actuals_markets_detailed(week: str) -> Dict[str, Any]:
    """Actuals per Market and Month. Not implemented yet."""
    return {"error": "Actuals markets detailed not implemented"}
