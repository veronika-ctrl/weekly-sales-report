from pathlib import Path

from weekly_report.src.storage.disk import (
    delete_ignored_pricing_uploads,
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
