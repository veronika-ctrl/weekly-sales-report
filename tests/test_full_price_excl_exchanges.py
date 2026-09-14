"""Full Price vs Sale excluding AfterShip exchanges — ingest, upsert, comparison."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.metrics.discounts_sales import (
    _is_revenue_over_time_format,
    load_revenue_over_time_history,
)
from weekly_report.src.metrics.full_price_excl_exchanges import (
    FILE_TYPE,
    calculate_full_price_vs_sale_excl_exchanges,
    compare_incl_excl,
    inspect_excl_exchanges_upload,
    load_full_price_vs_sale_excl_exchanges_history,
    missing_excl_exchanges_headers,
)


HEADERS = (
    "Date,Full Price,Compare-at Price Sale,Discount Code / Auto Discount,Both,"
    "Price Drop Sale,Total,Discount Amount,Full Price Share %,Exchange Orders,"
    "Exchange Gross Value,Exchange Discount,Exchange Net Revenue"
)


def _row(
    date: str,
    full: str = "100",
    compare: str = "0",
    code: str = "0",
    both: str = "0",
    drop: str = "0",
    total: str = "100",
    discount: str = "0",
    share: str = "100",
    orders: str = "0",
    egross: str = "0",
    edisc: str = "0",
    enet: str = "0",
) -> str:
    return ",".join(
        [date, full, compare, code, both, drop, total, discount, share, orders, egross, edisc, enet]
    )


def _write_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADERS + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _disable_fx(monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")


def test_missing_headers_error(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("Date,Full Price,Total\n2026-09-01,10,20\n", encoding="utf-8")
    df = pd.read_csv(path)
    missing = missing_excl_exchanges_headers(df)
    assert "Exchange Orders" in missing
    assert "Exchange Gross Value" in missing
    assert "Discount Amount" in missing
    inspected = inspect_excl_exchanges_upload(path)
    assert inspected["missing_headers"]
    assert "Exchange Discount" in inspected["missing_headers"]


def test_blank_numeric_becomes_zero(tmp_path: Path):
    dest = tmp_path / "raw" / "2026-36" / FILE_TYPE / "week.csv"
    _write_csv(
        dest,
        [_row("2026-09-01", full="", compare="", total="", discount="", share="", orders="", egross="", edisc="", enet="")],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    row = hist["df"].iloc[0]
    assert row["_full"] == 0.0
    assert row["_total"] == 0.0
    assert row["_discount"] == 0.0
    assert row["_exchange_orders"] == 0.0
    assert row["_exchange_gross"] == 0.0
    assert row["_full_price_share_pct"] == 0.0


def test_percentage_parsing(tmp_path: Path):
    dest = tmp_path / "raw" / "2026-36" / FILE_TYPE / "week.csv"
    _write_csv(
        dest,
        [
            _row("2026-09-01", full="45.2", total="100", share="45.2%"),
            _row("2026-09-02", full="45.2", total="100", share="45.2"),
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    shares = list(hist["df"]["_full_price_share_pct"])
    assert shares[0] == pytest.approx(45.2)
    assert shares[1] == pytest.approx(45.2)


def test_zero_sales_dates_preserved(tmp_path: Path):
    dest = tmp_path / "raw" / "2026-36" / FILE_TYPE / "week.csv"
    _write_csv(
        dest,
        [
            _row("2026-09-01", full="10", total="10"),
            _row("2026-09-02", full="0", total="0", discount="0", share="0"),
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    dates = [str(d.date()) for d in hist["df"]["_date"]]
    assert dates == ["2026-09-01", "2026-09-02"]
    zero = hist["df"][hist["df"]["_date"] == pd.Timestamp("2026-09-02")].iloc[0]
    assert zero["_total"] == 0.0


def test_upsert_by_date_replace_overlapping_append_new(tmp_path: Path):
    first = tmp_path / "raw" / "2026-35" / FILE_TYPE / "full-price-vs-sale-excl-exchanges-2026-08-24-to-2026-08-30.csv"
    _write_csv(
        first,
        [
            _row("2026-08-24", full="10", total="20", discount="1"),
            _row("2026-08-25", full="30", total="40", discount="2"),
        ],
    )
    first.touch()
    import time

    time.sleep(0.02)
    second = tmp_path / "raw" / "2026-36" / FILE_TYPE / "full-price-vs-sale-excl-exchanges-2026-08-25-to-2026-08-31.csv"
    _write_csv(
        second,
        [
            _row("2026-08-25", full="99", total="100", discount="9"),
            _row("2026-08-31", full="5", total="5", discount="0"),
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    by_date = {str(r["_date"].date()): r for _, r in hist["df"].iterrows()}
    assert set(by_date) == {"2026-08-24", "2026-08-25", "2026-08-31"}
    assert by_date["2026-08-24"]["_full"] == 10.0
    assert by_date["2026-08-25"]["_full"] == 99.0
    assert by_date["2026-08-25"]["_total"] == 100.0
    assert by_date["2026-08-31"]["_full"] == 5.0


def test_no_bleed_into_all_orders_history(tmp_path: Path):
    discounts = tmp_path / "raw" / "2026-36" / "discounts" / "all-orders.csv"
    discounts.parent.mkdir(parents=True)
    discounts.write_text(
        "Date,Full Price,Compare-at Price Sale,Total,Discount Amount\n"
        "2026-09-01,80,20,100,10\n",
        encoding="utf-8",
    )
    excl = tmp_path / "raw" / "2026-36" / FILE_TYPE / "excl.csv"
    _write_csv(excl, [_row("2026-09-01", full="50", total="60", discount="5", orders="2", egross="40")])

    all_hist = load_revenue_over_time_history(tmp_path)
    excl_hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    assert len(all_hist["df"]) == 1
    assert float(all_hist["df"].iloc[0]["_full"]) == 80.0
    assert float(all_hist["df"].iloc[0]["_total"]) == 100.0
    assert len(excl_hist["df"]) == 1
    assert float(excl_hist["df"].iloc[0]["_full"]) == 50.0


def test_exchange_csv_in_discounts_folder_is_not_all_orders(tmp_path: Path):
    misplaced = tmp_path / "raw" / "2026-36" / "discounts" / "excl-in-wrong-slot.csv"
    _write_csv(misplaced, [_row("2026-09-01", full="50", total="60", orders="3", egross="40")])
    df = pd.read_csv(misplaced)
    assert _is_revenue_over_time_format(df) is False
    hist = load_revenue_over_time_history(tmp_path)
    assert hist["df"].empty


def test_comparison_math():
    out = compare_incl_excl(
        excl_full=80.0,
        excl_total=100.0,
        excl_discount=10.0,
        exchange_gross=20.0,
        exchange_discount=5.0,
        incl_full=80.0,
        incl_total=120.0,
        incl_discount=15.0,
    )
    assert out["full_price_share_excl_pct"] == pytest.approx(80.0)
    assert out["full_price_share_incl_pct"] == pytest.approx(80.0 / 120.0 * 100.0)
    assert out["full_price_share_pp_diff"] == pytest.approx(80.0 - (80.0 / 120.0 * 100.0))
    assert out["total_incl"] == 120.0
    assert out["total_excl"] == 100.0
    assert out["discount_incl"] == 15.0
    assert out["discount_excl"] == 10.0
    # non_exchange_gross_est = 100+10=110; gross_context=110+20=130; share=20/130*100
    assert out["exchange_gross_share_pct"] == pytest.approx(20.0 / 130.0 * 100.0)
    assert out["exchange_discount_share_pct"] == pytest.approx(5.0 / 15.0 * 100.0)


def test_comparison_discount_share_fallback_without_all_orders():
    out = compare_incl_excl(
        excl_full=50.0,
        excl_total=100.0,
        excl_discount=8.0,
        exchange_gross=12.0,
        exchange_discount=4.0,
        incl_full=None,
        incl_total=None,
        incl_discount=None,
    )
    assert out["full_price_share_incl_pct"] is None
    assert out["exchange_discount_share_pct"] == pytest.approx(4.0 / (8.0 + 4.0) * 100.0)
    assert out["exchange_gross_share_pct"] == pytest.approx(12.0 / (100.0 + 8.0 + 12.0) * 100.0)


def test_period_and_daily_report(tmp_path: Path):
    dest = tmp_path / "raw" / "2026-36" / FILE_TYPE / "week.csv"
    # ISO week 2026-36 is 2026-08-31 .. 2026-09-06
    _write_csv(
        dest,
        [
            _row("2026-09-01", full="80", total="100", discount="10", share="80%", orders="2", egross="20", edisc="5", enet="0"),
            _row("2026-09-02", full="0", total="0", discount="0", share="0"),
        ],
    )
    all_orders = tmp_path / "raw" / "2026-36" / "discounts" / "all.csv"
    all_orders.parent.mkdir(parents=True, exist_ok=True)
    all_orders.write_text(
        "Date,Full Price,Total,Discount Amount\n2026-09-01,80,120,15\n2026-09-02,0,0,0\n",
        encoding="utf-8",
    )
    payload = calculate_full_price_vs_sale_excl_exchanges(
        "2026-36", tmp_path, num_weeks=1, granularity="week"
    )
    assert payload["period"] is not None
    assert payload["period"]["total"] == pytest.approx(100.0)
    assert payload["period"]["exchange_orders"] == 2
    assert payload["period"]["comparison"]["total_incl"] == pytest.approx(120.0)
    dates = [d["date"] for d in payload["days"]]
    assert "2026-09-01" in dates
    assert "2026-09-02" in dates
    day = next(d for d in payload["days"] if d["date"] == "2026-09-01")
    assert day["full_price"] == pytest.approx(80.0)
    assert day["comparison"]["exchange_gross_share_pct"] == pytest.approx(20.0 / 130.0 * 100.0)


def test_upload_rejects_missing_headers(tmp_path: Path, monkeypatch):
    import asyncio
    from io import BytesIO

    from starlette.datastructures import Headers, UploadFile

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    from weekly_report.api import routes

    monkeypatch.setattr(routes, "_supabase_enabled", lambda: False)

    async def _run():
        upload = UploadFile(
            file=BytesIO(b"Date,Full Price,Total\n2026-09-01,1,2\n"),
            filename="full-price-vs-sale-excl-exchanges-2026-09-01-to-2026-09-07.csv",
            headers=Headers({"content-type": "text/csv"}),
        )
        with pytest.raises(Exception) as exc:
            await routes.upload_file(file=upload, week="2026-36", file_type=FILE_TYPE)
        return exc.value

    err = asyncio.run(_run())
    detail = getattr(err, "detail", str(err))
    assert "Missing required headers" in str(detail)
    slot = tmp_path / "raw" / "2026-36" / FILE_TYPE
    assert not slot.exists() or list(slot.glob("*.csv")) == []


def test_upload_accepts_valid_headers_and_returns_date_range(tmp_path: Path, monkeypatch):
    import asyncio
    from io import BytesIO

    from starlette.datastructures import Headers, UploadFile

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    from weekly_report.api import routes

    monkeypatch.setattr(routes, "_supabase_enabled", lambda: False)
    body = (HEADERS + "\n" + _row("2026-09-01") + "\n" + _row("2026-09-03") + "\n").encode("utf-8")

    async def _run():
        upload = UploadFile(
            file=BytesIO(body),
            filename="full-price-vs-sale-excl-exchanges-2026-09-01-to-2026-09-07.csv",
            headers=Headers({"content-type": "text/csv"}),
        )
        return await routes.upload_file(file=upload, week="2026-36", file_type=FILE_TYPE)

    result = asyncio.run(_run())
    assert result["success"] is True
    assert result["date_range"] == {"start": "2026-09-01", "end": "2026-09-03"}
    saved = tmp_path / "raw" / "2026-36" / FILE_TYPE / "full-price-vs-sale-excl-exchanges-2026-09-01-to-2026-09-07.csv"
    assert saved.exists()
