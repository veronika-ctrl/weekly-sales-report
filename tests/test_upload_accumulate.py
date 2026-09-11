"""Upload slots: accumulate week+month aMER files; replace CAC/retention/Klaviyo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from weekly_report.src.storage.uploads import (
    ACCUMULATING_FILE_TYPES,
    REPLACE_ON_UPLOAD_FILE_TYPES,
    is_accumulating_file_type,
    list_slot_files,
    prepare_slot_for_upload,
    sanitize_upload_filename,
)

WEEK = "2026-36"
AMER_HEADER = "Channel;ChannelGroup;Country;Day;Revenue_CFA\nFacebook;social_ppc;Sweden;2026-08-31;1\n"


def _write(path: Path, name: str, body: str = AMER_HEADER) -> Path:
    dest = prepare_slot_for_upload(path, "amer_revenue", name)
    dest.write_text(body, encoding="utf-8")
    return dest


def test_amer_and_shopify_customers_accumulate():
    assert is_accumulating_file_type("amer_revenue")
    assert is_accumulating_file_type("amer_spend")
    assert is_accumulating_file_type("amer_gm2")
    assert is_accumulating_file_type("shopify_customers")
    assert is_accumulating_file_type("discounts")
    assert "amer_revenue" in ACCUMULATING_FILE_TYPES


def test_cac_retention_klaviyo_replace_on_upload():
    for file_type in REPLACE_ON_UPLOAD_FILE_TYPES:
        assert not is_accumulating_file_type(file_type)


def test_sanitize_keeps_veronika_shopify_filename():
    name = "Adjusted_aMER_customer_orders_-_2022-01-01_-_2026-09-09.csv"
    assert sanitize_upload_filename(name) == name


def test_amer_sequential_uploads_keep_w36_and_august(tmp_path: Path):
    slot = tmp_path / "raw" / WEEK / "amer_revenue"
    _write(slot, "Revenue_by_channel_W36.csv", AMER_HEADER)
    _write(slot, "Revenue_by_channel_2026-08.csv", AMER_HEADER)

    names = {p.name for p in list_slot_files(slot)}
    assert names == {
        "Revenue_by_channel_W36.csv",
        "Revenue_by_channel_2026-08.csv",
    }


def test_amer_same_filename_replaces_only_that_file(tmp_path: Path):
    slot = tmp_path / "raw" / WEEK / "amer_revenue"
    first = _write(slot, "Revenue_by_channel_W36.csv", "old,1\n")
    _write(slot, "Revenue_by_channel_2026-08.csv", AMER_HEADER)
    second = _write(slot, "Revenue_by_channel_W36.csv", "new,2\n")

    names = {p.name for p in list_slot_files(slot)}
    assert names == {
        "Revenue_by_channel_W36.csv",
        "Revenue_by_channel_2026-08.csv",
    }
    assert first == second
    assert second.read_text(encoding="utf-8") == "new,2\n"


def test_shopify_customers_keeps_history_files(tmp_path: Path):
    slot = tmp_path / "raw" / WEEK / "shopify_customers"
    first = "Adjusted_aMER_customer_orders_-_2022-01-01_-_2026-09-09.csv"
    prepare_slot_for_upload(slot, "shopify_customers", first).write_text("a", encoding="utf-8")
    prepare_slot_for_upload(slot, "shopify_customers", "extra_history.csv").write_text("b", encoding="utf-8")
    names = {p.name for p in list_slot_files(slot)}
    assert names == {first, "extra_history.csv"}


def test_replace_type_wipes_previous_file(tmp_path: Path):
    slot = tmp_path / "raw" / WEEK / "klaviyo_email"
    prepare_slot_for_upload(slot, "klaviyo_email", "old.csv").write_text("a", encoding="utf-8")
    prepare_slot_for_upload(slot, "klaviyo_email", "new.csv").write_text("b", encoding="utf-8")
    names = {p.name for p in list_slot_files(slot)}
    assert names == {"new.csv"}


def _upload(routes, filename: str, file_type: str, body: str, week: str = WEEK):
    from io import BytesIO
    from starlette.datastructures import Headers, UploadFile

    upload = UploadFile(
        file=BytesIO(body.encode("utf-8")),
        filename=filename,
        headers=Headers({"content-type": "text/csv"}),
    )
    return routes.upload_file(file=upload, week=week, file_type=file_type)


@pytest.fixture
def upload_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    from weekly_report.api import routes

    monkeypatch.setattr(routes, "_supabase_enabled", lambda: False)
    return routes, tmp_path


def test_upload_endpoint_amer_accumulates_w36_and_august(upload_env):
    import asyncio

    routes, data_root = upload_env

    async def _run():
        for name in ("Revenue_by_channel_W36.csv", "Revenue_by_channel_2026-08.csv"):
            result = await _upload(routes, name, "amer_revenue", AMER_HEADER)
            assert result["success"] is True
        response = await routes.get_file_metadata(week=WEEK)
        return json.loads(response.body)

    payload = asyncio.run(_run())["amer_revenue"]
    slot = data_root / "raw" / WEEK / "amer_revenue"
    names = {p.name for p in list_slot_files(slot)}
    assert names == {
        "Revenue_by_channel_W36.csv",
        "Revenue_by_channel_2026-08.csv",
    }
    listed = {f["filename"] for f in payload["files"]}
    assert listed == names
    assert payload["accumulates"] is True


def test_upload_endpoint_klaviyo_replaces(upload_env):
    import asyncio

    routes, data_root = upload_env
    header = "Campaign Name;Date\nA;2026-01-01\n"

    async def _run():
        for name in ("klaviyo_old.csv", "klaviyo_new.csv"):
            result = await _upload(routes, name, "klaviyo_email", header)
            assert result["success"] is True
        response = await routes.get_file_metadata(week=WEEK)
        return json.loads(response.body)

    payload = asyncio.run(_run())["klaviyo_email"]
    slot = data_root / "raw" / WEEK / "klaviyo_email"
    names = {p.name for p in list_slot_files(slot)}
    assert names == {"klaviyo_new.csv"}
    assert [f["filename"] for f in payload["files"]] == ["klaviyo_new.csv"]
    assert payload["accumulates"] is False
