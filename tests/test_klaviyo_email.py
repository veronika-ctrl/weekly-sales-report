"""Tests for Klaviyo email performance report."""

from __future__ import annotations

from pathlib import Path

from weekly_report.src.metrics.klaviyo_email import (
    HEADER_NOTE,
    KLAVIYO_EMAIL_TYPE,
    calculate_klaviyo_email,
)

CSV = """Type,Name,Recipients,UniqueConverters,Conversions,RevenueUSD
Flow,Welcome to Newsletter,100,10,11,200.5
Flow,Abandoned Checkout,50,5,5,80
Flow,Zero Flow,20,0,0,0
Campaign,All newsletter campaigns (210 campaigns aggregated),1000,40,40,500
"""


def test_metrics_list_omits_page_size(monkeypatch):
    captured = {}

    class DummyResp:
        def read(self):
            return b'{"data":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return DummyResp()

    monkeypatch.setenv("KLAVIYO_PRIVATE_API_KEY", "pk_test_placeholder_not_real")
    monkeypatch.setattr("weekly_report.src.klaviyo_client.urllib.request.urlopen", fake_urlopen)
    from weekly_report.src.klaviyo_client import probe_connection, find_placed_order_metric_id

    ok, err = probe_connection()
    assert ok is True
    assert err is None
    assert "page[size]" not in captured["url"]
    assert "page_size" not in captured["url"]
    try:
        find_placed_order_metric_id()
    except RuntimeError:
        pass
    assert "page[size]" not in captured["url"]
    assert "fields[metric]" in captured["url"]


def test_empty(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KLAVIYO_PRIVATE_API_KEY", raising=False)
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "true")
    payload = calculate_klaviyo_email(tmp_path)
    assert payload["available"] is False
    assert payload["header_note"] == HEADER_NOTE
    assert "aMER" in payload["header_note"]


def test_csv_flows_sorted_newsletter_separate(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KLAVIYO_PRIVATE_API_KEY", raising=False)
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "true")
    path = tmp_path / "raw" / "2026-36" / KLAVIYO_EMAIL_TYPE / "Klaviyo_email_performance_last12m.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CSV, encoding="utf-8")
    payload = calculate_klaviyo_email(tmp_path)
    assert payload["available"] is True
    assert payload["source"] == "csv"
    names = [r["name"] for r in payload["flows"]]
    assert names[0] == "Welcome to Newsletter"
    assert names[-1] == "Zero Flow"
    assert "All newsletter" not in "".join(names)
    nl = payload["newsletter"]
    assert nl["is_newsletter"] is True
    assert nl["campaign_count"] == 210
    assert nl["recipients"] == 1000
    assert payload["total"]["recipients"] == 1170
    assert payload["total"]["unique_converters"] == 55
    assert abs(payload["total"]["revenue_usd"] - 780.5) < 1e-6
    welcome = payload["flows"][0]
    assert welcome["conversion_rate"] == 0.1
    assert welcome["revenue_sek"] is None


def test_sek_conversion_uses_fallback_rate(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KLAVIYO_PRIVATE_API_KEY", raising=False)
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "true")  # replaced below via patch

    def fake_rate(_data_root: Path):
        return 10.0, {
            "applied": True,
            "source_currency": "USD",
            "target_currency": "SEK",
            "provider": "fallback_env",
            "sample_rate": 10.0,
            "error": None,
        }

    monkeypatch.setattr(
        "weekly_report.src.metrics.klaviyo_email.get_latest_usd_sek_rate",
        fake_rate,
    )
    path = tmp_path / "raw" / "2026-36" / KLAVIYO_EMAIL_TYPE / "klaviyo.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CSV, encoding="utf-8")
    payload = calculate_klaviyo_email(tmp_path)
    assert payload["fx"]["applied"] is True
    assert payload["fx"]["sample_rate"] == 10
    assert abs(payload["total"]["revenue_sek"] - 7805.0) < 1e-6
    assert abs(payload["newsletter"]["revenue_sek"] - 5000.0) < 1e-6
