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
HEADERS_WITH_OPTIONAL = HEADERS + ",Subscription Discount,Markdown Amount"


def _row(
    date: str,
    full: str = "100",
    compare: str | None = None,
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
    subscription: str | None = None,
    markdown: str | None = None,
) -> str:
    if compare is None:
        try:
            compare = str(float(total or 0) - float(full or 0))
        except ValueError:
            compare = "0"
    cells = [date, full, compare, code, both, drop, total, discount, share, orders, egross, edisc, enet]
    if subscription is not None or markdown is not None:
        cells.append(subscription if subscription is not None else "0")
        cells.append(markdown if markdown is not None else "0")
    return ",".join(cells)


def _write_csv(path: Path, rows: list[str], *, headers: str = HEADERS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(headers + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def _slot(tmp_path: Path, week: str = "2026-36", name: str = "september_2026.csv") -> Path:
    return tmp_path / "raw" / week / FILE_TYPE / name


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
    dest = _slot(tmp_path)
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
    dest = _slot(tmp_path)
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
    dest = _slot(tmp_path)
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


def test_own_month_wins_and_extra_days_are_dropped(tmp_path: Path):
    """August file may include extra September days; September file owns Sep dates."""
    august = _slot(tmp_path, "2026-41", "august_2026_full_exchanges.csv")
    _write_csv(
        august,
        [
            _row("2026-08-24", full="10", total="20", discount="1"),
            _row("2026-08-25", full="30", total="40", discount="2"),
            _row("2026-09-01", full="1", total="1", discount="0"),  # extra day — ignore
        ],
    )
    september = _slot(tmp_path, "2026-41", "september_2026.csv")
    _write_csv(
        september,
        [
            _row("2026-09-01", full="99", total="100", discount="9"),
            _row("2026-09-02", full="5", total="5", discount="0"),
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    by_date = {str(r["_date"].date()): r for _, r in hist["df"].iterrows()}
    assert set(by_date) == {"2026-08-24", "2026-08-25", "2026-09-01", "2026-09-02"}
    assert by_date["2026-08-24"]["_full"] == 10.0
    assert by_date["2026-09-01"]["_full"] == 99.0
    assert by_date["2026-09-01"]["_total"] == 100.0


def test_legacy_weekly_names_are_ignored(tmp_path: Path):
    old = tmp_path / "raw" / "2026-40" / FILE_TYPE / "Full_Price_vs_Sale_W40.csv"
    _write_csv(old, [_row("2026-09-28", full="50", total="100")])
    exch = tmp_path / "raw" / "2026-40" / FILE_TYPE / "Exchanges_W40.csv"
    _write_csv(exch, [_row("2026-09-29", full="1", total="1")])
    hist_name = tmp_path / "raw" / "2026-40" / FILE_TYPE / "Exchanges_Historical_Data.csv"
    _write_csv(hist_name, [_row("2026-09-30", full="2", total="2")])
    dated = tmp_path / "raw" / "2026-40" / FILE_TYPE / "full-price-vs-sale-2024-01-01-to-2024-01-07.csv"
    _write_csv(dated, [_row("2024-01-01", full="3", total="3")])
    month = _slot(tmp_path, "2026-41", "september_2026.csv")
    _write_csv(month, [_row("2026-09-15", full="80", total="100")])
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    dates = [str(d.date()) for d in hist["df"]["_date"]]
    assert dates == ["2026-09-15"]
    assert "Full_Price_vs_Sale_W40.csv" in hist.get("ignored_files", [])
    assert any("W40" in n for n in hist.get("ignored_files", []))


def test_discounts_slot_is_not_read(tmp_path: Path):
    discounts = tmp_path / "raw" / "2026-36" / "discounts" / "all-orders.csv"
    discounts.parent.mkdir(parents=True)
    discounts.write_text(
        "Date,Full Price,Compare-at Price Sale,Total,Discount Amount\n"
        "2026-09-01,80,20,100,10\n",
        encoding="utf-8",
    )
    stray_month = tmp_path / "raw" / "2026-36" / "discounts" / "august_2026_full_exchanges.csv"
    _write_csv(stray_month, [_row("2026-08-15", full="1", total="1")])
    excl = _slot(tmp_path, "2026-41", "september_2026.csv")
    _write_csv(excl, [_row("2026-09-01", full="50", total="60", discount="5", orders="2", egross="40")])

    all_hist = load_revenue_over_time_history(tmp_path)
    excl_hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    assert len(all_hist["df"]) == 1
    assert float(all_hist["df"].iloc[0]["_full"]) == 50.0
    assert float(all_hist["df"].iloc[0]["_total"]) == 60.0
    assert float(all_hist["df"].iloc[0]["_discounted"]) == pytest.approx(10.0)
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
    assert out["discounted_share_excl_pct"] == pytest.approx(20.0)
    assert out["discounted_share_incl_pct"] == pytest.approx(100.0 - (80.0 / 120.0 * 100.0))
    assert out["discounted_share_pp_diff"] == pytest.approx(-out["full_price_share_pp_diff"])
    assert out["discount_rate_excl_pct"] == pytest.approx(10.0 / 110.0 * 100.0)
    assert out["discount_rate_incl_pct"] == pytest.approx(15.0 / 135.0 * 100.0)
    assert out["discount_rate_pp_diff"] == pytest.approx(
        (10.0 / 110.0 * 100.0) - (15.0 / 135.0 * 100.0)
    )
    assert out["total_incl"] == 120.0
    assert out["total_excl"] == 100.0
    assert out["full_incl"] == 80.0
    assert out["full_excl"] == 80.0
    assert out["discounted_incl"] == pytest.approx(40.0)
    assert out["discounted_excl"] == pytest.approx(20.0)
    assert out["discount_incl"] == 15.0
    assert out["discount_excl"] == 10.0
    # non_exchange_gross_est = 100+10=110; gross_context=110+20=130; share=20/130*100
    assert out["exchange_gross_share_pct"] == pytest.approx(20.0 / 130.0 * 100.0)
    assert out["exchange_discount_share_pct"] == pytest.approx(5.0 / 15.0 * 100.0)
    assert out["promotional_discount_share_pct"] == pytest.approx(10.0 / 15.0 * 100.0)
    # 100% sales mix: denom = excl. Total + exchange gross (not net, not discount amount).
    assert out["sales_mix_denom"] == pytest.approx(120.0)
    assert out["sales_mix_full_price_pct"] == pytest.approx(80.0 / 120.0 * 100.0)
    assert out["sales_mix_exchange_pct"] == pytest.approx(20.0 / 120.0 * 100.0)
    assert out["sales_mix_promo_pct"] == pytest.approx(20.0 / 120.0 * 100.0)
    assert (
        out["sales_mix_full_price_pct"]
        + out["sales_mix_exchange_pct"]
        + out["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)


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
    assert out["full_incl"] is None
    assert out["full_excl"] == pytest.approx(50.0)
    assert out["discounted_incl"] is None
    assert out["discounted_excl"] == pytest.approx(50.0)
    assert out["exchange_discount_share_pct"] == pytest.approx(4.0 / (8.0 + 4.0) * 100.0)
    assert out["exchange_gross_share_pct"] == pytest.approx(12.0 / (100.0 + 8.0 + 12.0) * 100.0)
    assert out["sales_mix_denom"] == pytest.approx(112.0)
    assert out["sales_mix_exchange_pct"] == pytest.approx(12.0 / 112.0 * 100.0)
    assert (
        out["sales_mix_full_price_pct"]
        + out["sales_mix_exchange_pct"]
        + out["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)


def test_period_and_daily_report(tmp_path: Path):
    dest = _slot(tmp_path)
    # ISO week 2026-36 is 2026-08-31 .. 2026-09-06
    _write_csv(
        dest,
        [
            _row("2026-09-01", full="80", total="100", discount="10", share="80%", orders="2", egross="20", edisc="5", enet="0"),
            _row("2026-09-02", full="0", total="0", discount="0", share="0"),
        ],
    )
    payload = calculate_full_price_vs_sale_excl_exchanges(
        "2026-36", tmp_path, num_weeks=1, granularity="week"
    )
    assert payload["period"] is not None
    assert payload["period"]["total"] == pytest.approx(100.0)
    assert payload["period"]["exchange_orders"] == 2
    assert payload["period"]["discounted"] == pytest.approx(20.0)
    # All-orders discount reconstructed from the same file: 10 + 5.
    assert payload["period"]["comparison"]["discount_incl"] == pytest.approx(15.0)
    assert payload["period"]["comparison"]["total_incl"] == pytest.approx(100.0)
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


def test_weekly_series_period_total_is_not_latest_week_and_mix_stays_flat(tmp_path: Path):
    """8-week (here: 2-week) window share ≠ latest week; excluding 0-net exchanges does not lift FP%."""
    # ISO 2026-36 = Mon 2026-08-31; 2026-37 = Mon 2026-09-07.
    dest = _slot(tmp_path, "2026-37", "september_2026.csv")
    _write_csv(
        dest,
        [
            # W36: 80% full price, no exchange net
            _row(
                "2026-09-01",
                full="80",
                total="100",
                discount="5",
                share="80",
                orders="2",
                egross="5",
                edisc="5",
                enet="0",
            ),
            # W37: 40% full price; AfterShip credit is in Discount Amount of all-orders,
            # but exchange net is 0 so dropping the order does not change mix.
            _row(
                "2026-09-08",
                full="40",
                total="100",
                discount="10",
                share="40",
                orders="3",
                egross="20",
                edisc="20",
                enet="0",
            ),
        ],
    )
    payload = calculate_full_price_vs_sale_excl_exchanges(
        "2026-37", tmp_path, num_weeks=2, granularity="week"
    )
    weeks = {w["week"]: w for w in payload["weeks"]}
    w36 = weeks["2026-36"]
    w37 = weeks["2026-37"]
    period = payload["period"]
    assert period is not None

    assert w36["comparison"]["full_price_share_incl_pct"] == pytest.approx(80.0)
    assert w36["comparison"]["full_price_share_excl_pct"] == pytest.approx(80.0)
    assert w37["comparison"]["full_price_share_incl_pct"] == pytest.approx(40.0)
    assert w37["comparison"]["full_price_share_excl_pct"] == pytest.approx(40.0)
    # Window total 120/200 = 60%, not the latest week's 40%.
    assert period["comparison"]["full_price_share_incl_pct"] == pytest.approx(60.0)
    assert period["comparison"]["full_price_share_excl_pct"] == pytest.approx(60.0)
    assert period["comparison"]["full_price_share_incl_pct"] != pytest.approx(
        w37["comparison"]["full_price_share_incl_pct"]
    )
    # Mix is unchanged (exchange net = 0); discount amount is what exchanges distort.
    assert w37["comparison"]["full_price_share_pp_diff"] == pytest.approx(0.0)
    assert period["comparison"]["discount_incl"] == pytest.approx(40.0)
    assert period["comparison"]["discount_excl"] == pytest.approx(15.0)
    assert period["comparison"]["exchange_discount_share_pct"] == pytest.approx(25.0 / 40.0 * 100.0)
    # Split amounts for the before/after bar chart.
    assert w37["comparison"]["full_incl"] == pytest.approx(40.0)
    assert w37["comparison"]["full_excl"] == pytest.approx(40.0)
    assert w37["comparison"]["discounted_incl"] == pytest.approx(60.0)
    assert w37["comparison"]["discounted_excl"] == pytest.approx(60.0)
    # 100% sales mix: exchange gross is in the mix even though net is 0.
    assert w37["exchange_net_revenue"] == pytest.approx(0.0)
    assert w37["exchange_gross_value"] == pytest.approx(20.0)
    mix = w37["comparison"]
    assert mix["sales_mix_denom"] == pytest.approx(120.0)
    assert mix["sales_mix_full_price_pct"] == pytest.approx(40.0 / 120.0 * 100.0)
    assert mix["sales_mix_exchange_pct"] == pytest.approx(20.0 / 120.0 * 100.0)
    assert mix["sales_mix_promo_pct"] == pytest.approx(60.0 / 120.0 * 100.0)
    assert mix["sales_mix_exchange_pct"] > 0
    assert (
        mix["sales_mix_full_price_pct"]
        + mix["sales_mix_exchange_pct"]
        + mix["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)
    # Window: excl full 120, excl total 200, exchange gross 25 → denom 225.
    period_mix = period["comparison"]
    assert period_mix["sales_mix_denom"] == pytest.approx(225.0)
    assert (
        period_mix["sales_mix_full_price_pct"]
        + period_mix["sales_mix_exchange_pct"]
        + period_mix["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)


def test_sales_mix_is_share_of_sales_not_share_of_discount():
    """Exchange credits can dominate discount amount while remaining a small sales slice."""
    out = compare_incl_excl(
        excl_full=848927.0,
        excl_total=1320856.0,
        excl_discount=19524.0,
        exchange_gross=27516.0,
        exchange_discount=27516.0,
        incl_full=848927.0,
        incl_total=1320856.0,
        incl_discount=47040.0,
    )
    assert out["exchange_discount_share_pct"] == pytest.approx(27516.0 / 47040.0 * 100.0)
    assert out["exchange_discount_share_pct"] > 50
    assert out["sales_mix_exchange_pct"] == pytest.approx(27516.0 / (1320856.0 + 27516.0) * 100.0)
    assert out["sales_mix_exchange_pct"] < 5
    assert (
        out["sales_mix_full_price_pct"]
        + out["sales_mix_exchange_pct"]
        + out["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)


def test_monthly_before_after_series(tmp_path: Path):
    _write_csv(
        _slot(tmp_path, "2026-41", "august_2026.csv"),
        [
            _row("2026-08-15", full="70", total="100", discount="5", share="70", orders="1", egross="8", edisc="8", enet="0"),
        ],
    )
    _write_csv(
        _slot(tmp_path, "2026-41", "september_2026.csv"),
        [
            _row("2026-09-08", full="50", total="100", discount="6", share="50", orders="1", egross="9", edisc="9", enet="0"),
        ],
    )
    payload = calculate_full_price_vs_sale_excl_exchanges(
        "2026-37", tmp_path, months=2, granularity="month"
    )
    by_month = {m["month"]: m for m in payload["months_data"]}
    assert by_month["2026-08"]["comparison"]["full_price_share_incl_pct"] == pytest.approx(70.0)
    assert by_month["2026-08"]["comparison"]["full_price_share_excl_pct"] == pytest.approx(70.0)
    assert by_month["2026-09"]["comparison"]["full_price_share_incl_pct"] == pytest.approx(50.0)
    assert by_month["2026-09"]["comparison"]["full_price_share_excl_pct"] == pytest.approx(50.0)
    # Aug+Sep window ≠ September alone.
    assert payload["period"]["comparison"]["full_price_share_incl_pct"] == pytest.approx(60.0)
    sep = by_month["2026-09"]["comparison"]
    assert sep["sales_mix_exchange_pct"] == pytest.approx(9.0 / 109.0 * 100.0)
    assert sep["sales_mix_exchange_pct"] > 0
    assert (
        sep["sales_mix_full_price_pct"] + sep["sales_mix_exchange_pct"] + sep["sales_mix_promo_pct"]
    ) == pytest.approx(100.0)


def test_optional_headers_missing_are_zero_not_a_hard_fail(tmp_path: Path):
    dest = _slot(tmp_path, "2026-41", "september_2026.csv")
    _write_csv(dest, [_row("2026-09-01", full="80", total="100", discount="10")])
    inspected = inspect_excl_exchanges_upload(dest)
    assert inspected["missing_headers"] == []
    assert inspected["optional_headers_present"]["Subscription Discount"] is False
    assert inspected["optional_headers_present"]["Markdown Amount"] is False
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    row = hist["df"].iloc[0]
    assert row["_subscription"] == 0.0
    assert row["_markdown"] == 0.0
    assert row["_discounted"] == pytest.approx(20.0)
    assert row["_discount"] == pytest.approx(10.0)


def test_discounted_is_explicit_sum_including_subscription(tmp_path: Path):
    dest = _slot(tmp_path, "2026-41", "september_2026.csv")
    _write_csv(
        dest,
        [
            _row(
                "2026-09-01",
                full="50",
                compare="10",
                code="5",
                both="3",
                drop="2",
                total="80",
                discount="4",
                subscription="7",
                markdown="1",
            )
        ],
        headers=HEADERS_WITH_OPTIONAL,
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    row = hist["df"].iloc[0]
    # 10+5+7+3+2 = 27, not Total−Full (30).
    assert row["_discounted"] == pytest.approx(27.0)
    assert row["_discount"] == pytest.approx(5.0)  # 4 + 1 markdown
    assert row["_all_orders_discount"] == pytest.approx(4.0)  # discount amount + exchange 0
    payload = calculate_full_price_vs_sale_excl_exchanges("2026-36", tmp_path, num_weeks=1)
    assert payload["period"]["discounted"] == pytest.approx(27.0)
    assert payload["period"]["subscription_discount"] == pytest.approx(7.0)
    assert payload["period"]["full_price_share_pct"] == pytest.approx(50.0 / 80.0 * 100.0)


def test_typo_and_short_year_month_filenames(tmp_path: Path):
    from weekly_report.src.metrics.pricing_history import parse_month_from_filename

    assert parse_month_from_filename("january_2026_ful_exchanges.csv") == (2026, 1)
    assert parse_month_from_filename("september_full_26.csv") == (2026, 9)
    assert parse_month_from_filename("august_2026_full_exchanges.csv") == (2026, 8)
    assert parse_month_from_filename("Full_Price_vs_Sale_W40.csv") is None
    jan = _slot(tmp_path, "2026-41", "january_2026_ful_exchanges.csv")
    _write_csv(
        jan,
        [
            _row("2026-01-15", full="40", total="100"),
            _row("2026-02-01", full="1", total="1"),  # extra day after January
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    dates = [str(d.date()) for d in hist["df"]["_date"]]
    assert dates == ["2026-01-15"]


def test_weekly_continuation_file_keeps_mon_sun_only(tmp_path: Path):
    # ISO 2026-41 = Mon 2026-10-05 .. Sun 2026-10-11. Export often has +2 extra days.
    dest = _slot(tmp_path, "2026-41", "week_2026_41.csv")
    _write_csv(
        dest,
        [
            _row("2026-10-05", full="10", total="10"),
            _row("2026-10-11", full="20", total="20"),
            _row("2026-10-12", full="99", total="99"),
            _row("2026-10-13", full="88", total="88"),
        ],
    )
    hist = load_full_price_vs_sale_excl_exchanges_history(tmp_path)
    dates = [str(d.date()) for d in hist["df"]["_date"]]
    assert dates == ["2026-10-05", "2026-10-11"]
