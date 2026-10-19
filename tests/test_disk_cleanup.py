from pathlib import Path

from weekly_report.src.storage.disk import (
    delete_ignored_pricing_uploads,
    delete_stale_weeks_36_to_40,
    disk_usage_payload,
    is_disk_full_error,
    is_ignored_pricing_upload,
    list_ignored_pricing_uploads,
)


def _touch(path: Path, size: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_ignored_old_weekly_names_and_discounts_slot(tmp_path: Path):
    keep_month = tmp_path / "raw" / "2026-41" / "full_price_vs_sale_excl_exchanges" / "august_2026_full_exchanges.csv"
    keep_qlik = tmp_path / "raw" / "2026-41" / "qlik" / "Qlik_W41.csv"
    old_discounts = tmp_path / "raw" / "2026-40" / "discounts" / "Full_Price_vs_Sale_W40.csv"
    old_excl = tmp_path / "raw" / "2026-40" / "full_price_vs_sale_excl_exchanges" / "Exchanges_W40.csv"
    old_hist = tmp_path / "raw" / "2026-37" / "full_price_vs_sale_excl_exchanges" / "Exchanges_Historical_Data.csv"
    wrong_slot = tmp_path / "raw" / "2026-41" / "discounts" / "august_2026_full_exchanges.csv"
    dema = tmp_path / "raw" / "2026-42" / "dema_spend" / "Dema_Marketing_Spend_W42.csv"
    for p, n in (
        (keep_month, 50),
        (keep_qlik, 40),
        (old_discounts, 30),
        (old_excl, 20),
        (old_hist, 15),
        (wrong_slot, 25),
        (dema, 12),
    ):
        _touch(p, n)

    assert is_ignored_pricing_upload(old_discounts)
    assert is_ignored_pricing_upload(old_excl)
    assert is_ignored_pricing_upload(old_hist)
    assert is_ignored_pricing_upload(wrong_slot)
    assert not is_ignored_pricing_upload(keep_month)
    assert not is_ignored_pricing_upload(keep_qlik)
    assert not is_ignored_pricing_upload(dema)

    ignored = {row["path"] for row in list_ignored_pricing_uploads(tmp_path)}
    assert "raw/2026-40/discounts/Full_Price_vs_Sale_W40.csv" in ignored
    assert "raw/2026-40/full_price_vs_sale_excl_exchanges/Exchanges_W40.csv" in ignored
    assert "raw/2026-41/full_price_vs_sale_excl_exchanges/august_2026_full_exchanges.csv" not in ignored

    result = delete_ignored_pricing_uploads(tmp_path)
    assert result["count"] == 4
    assert keep_month.exists()
    assert keep_qlik.exists()
    assert dema.exists()
    assert not old_discounts.exists()
    assert not old_excl.exists()
    assert not old_hist.exists()
    assert not wrong_slot.exists()


def test_disk_usage_flags_ignored_bytes(tmp_path: Path):
    _touch(tmp_path / "raw" / "2026-40" / "discounts" / "Full_Price_vs_Sale_W40.csv", 100)
    _touch(tmp_path / "raw" / "2026-41" / "qlik" / "Qlik_W41.csv", 40)
    payload = disk_usage_payload(tmp_path)
    assert payload["ignored_count"] == 1
    assert payload["ignored_bytes"] == 100
    assert payload["raw_bytes"] == 140
    assert payload["free_bytes"] >= 0
    assert "used_pct" in payload


def test_is_disk_full_error():
    assert is_disk_full_error(OSError(28, "No space left on device"))
    assert is_disk_full_error(OSError("No space left on device"))
    assert not is_disk_full_error(OSError(2, "No such file or directory"))
    assert not is_disk_full_error(ValueError("bad csv"))


def test_disk_usage_and_delete_endpoints(tmp_path: Path, monkeypatch):
    import asyncio

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    keep = tmp_path / "raw" / "2026-41" / "full_price_vs_sale_excl_exchanges" / "august_2026_full_exchanges.csv"
    old = tmp_path / "raw" / "2026-40" / "discounts" / "Full_Price_vs_Sale_W40.csv"
    _touch(keep, 40)
    _touch(old, 80)
    from weekly_report.api import routes

    usage = asyncio.run(routes.get_disk_usage())
    assert usage["ignored_count"] == 1
    assert usage["ignored_bytes"] == 80
    result = asyncio.run(routes.post_delete_ignored_pricing_files())
    assert result["count"] == 1
    assert keep.exists()
    assert not old.exists()
    assert result["disk"]["ignored_count"] == 0


def test_delete_weeks_36_to_40_keeps_history_and_drops_qlik(tmp_path: Path):
    qlik = tmp_path / "raw" / "2026-36" / "qlik" / "Qlik_W36.xlsx"
    dema = tmp_path / "raw" / "2026-40" / "dema_spend" / "Dema_Marketing_Spend_W40.csv"
    sessions = tmp_path / "raw" / "2026-38" / "shopify" / "Sessions_W38.csv"
    customers = tmp_path / "raw" / "2026-36" / "shopify_customers" / "customers.csv"
    august = tmp_path / "raw" / "2026-36" / "amer_revenue" / "Revenue_by_channel_2026-08.csv"
    weekly_amer = tmp_path / "raw" / "2026-36" / "amer_revenue" / "Revenue_by_channel_W36.csv"
    month_fp = tmp_path / "raw" / "2026-41" / "full_price_vs_sale_excl_exchanges" / "august_2026_full_exchanges.csv"
    w41_qlik = tmp_path / "raw" / "2026-41" / "qlik" / "Qlik_W41.csv"
    for p, n in (
        (qlik, 200),
        (dema, 80),
        (sessions, 50),
        (customers, 30),
        (august, 25),
        (weekly_amer, 20),
        (month_fp, 15),
        (w41_qlik, 40),
    ):
        _touch(p, n)

    payload = disk_usage_payload(tmp_path)
    assert payload["stale_week_count"] == 4
    assert payload["stale_week_bytes"] == 200 + 80 + 50 + 20

    result = delete_stale_weeks_36_to_40(tmp_path)
    assert result["bytes_freed"] == 200 + 80 + 50 + 20
    assert not qlik.exists()
    assert not dema.exists()
    assert not sessions.exists()
    assert not weekly_amer.exists()
    assert (tmp_path / "raw" / "2026-41" / "shopify_customers" / "customers.csv").exists()
    assert (tmp_path / "raw" / "2026-41" / "amer_revenue" / "Revenue_by_channel_2026-08.csv").exists()
    assert month_fp.exists()
    assert w41_qlik.exists()
    assert not (tmp_path / "raw" / "2026-36").exists()
    assert not (tmp_path / "raw" / "2026-40").exists()


def test_delete_weeks_36_to_40_endpoint(tmp_path: Path, monkeypatch):
    import asyncio

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    _touch(tmp_path / "raw" / "2026-37" / "qlik" / "Qlik_W37.csv", 90)
    _touch(tmp_path / "raw" / "2026-41" / "qlik" / "Qlik_W41.csv", 10)
    from weekly_report.api import routes

    result = asyncio.run(routes.post_delete_weeks_36_to_40())
    assert result["count"] == 1
    assert result["bytes_freed"] == 90
    assert not (tmp_path / "raw" / "2026-37").exists()
    assert (tmp_path / "raw" / "2026-41" / "qlik" / "Qlik_W41.csv").exists()
