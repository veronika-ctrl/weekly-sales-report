#!/usr/bin/env python3
"""Run budget MTD debug logic and print JSON (same as GET /api/budget-mtd-debug)."""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Project root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("DATA_ROOT", str(root / "data"))

try:
    from dotenv import load_dotenv
    load_dotenv(root / ".env")
except ImportError:
    pass

from weekly_report.src.config import load_config
from weekly_report.src.periods.calculator import get_week_date_range, validate_iso_week
import weekly_report.api.routes as routes
import pandas as pd

def main():
    base_week = sys.argv[1] if len(sys.argv) > 1 else "2026-11"
    if not validate_iso_week(base_week):
        print(json.dumps({"ok": False, "error": "Invalid ISO week"}))
        return
    config = load_config(week=base_week)
    week_range = get_week_date_range(base_week)
    end_dt = datetime.strptime(week_range["end"], "%Y-%m-%d")
    target_month = end_dt.strftime("%B %Y")
    data_root = Path(config.data_root).resolve()
    raw = data_root / "raw"
    tried_paths = []
    if raw.exists():
        tried_paths.append(str((raw / base_week / "budget").resolve()))
        year = int(base_week.split("-")[0])
        for p in sorted(raw.iterdir(), reverse=True):
            if p.is_dir() and p.name.startswith(str(year) + "-"):
                tried_paths.append(str((p / "budget").resolve()))
                break
        tried_paths.append(str((raw / "budget").resolve()))
    mtd_budget = routes._load_mtd_budget_direct(base_week, Path(config.data_root))
    has_values = bool(
        mtd_budget
        and any(
            v != 0
            for k, v in (mtd_budget or {}).items()
            if isinstance(v, (int, float))
        )
    )
    csv_path = None
    if raw.exists():
        for check in [raw / base_week / "budget", raw / "budget"]:
            if check.exists():
                csvs = [f for f in check.glob("*.csv") if not f.name.startswith(".")]
                if csvs:
                    csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
                    break
        if csv_path is None:
            year = int(base_week.split("-")[0])
            for p in sorted(raw.iterdir(), reverse=True):
                if p.is_dir() and p.name.startswith(str(year) + "-"):
                    bd = p / "budget"
                    if bd.exists():
                        csvs = [f for f in bd.glob("*.csv") if not f.name.startswith(".")]
                        if csvs:
                            csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
                            break
    preview = {}
    if csv_path:
        try:
            df = pd.read_csv(
                csv_path, encoding="utf-8-sig", sep=None, engine="python", nrows=5
            )
            df.columns = df.columns.str.replace("\ufeff", "").str.strip()
            preview = {
                "file": str(csv_path),
                "columns": list(df.columns),
                "row_count_preview": len(df),
                "first_row": df.iloc[0].astype(str).to_dict() if len(df) > 0 else None,
            }
        except Exception as e:
            preview = {"file": str(csv_path), "error": str(e)}
    out = {
        "ok": has_values,
        "base_week": base_week,
        "target_month": target_month,
        "data_root_resolved": str(data_root),
        "tried_paths": tried_paths,
        "mtd_budget_sample": dict(list((mtd_budget or {}).items())[:8]),
        "has_mtd_budget": has_values,
        "preview": preview,
    }
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
