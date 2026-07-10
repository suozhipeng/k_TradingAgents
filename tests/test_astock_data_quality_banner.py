"""Tests for DataQualityBanner."""

from datetime import datetime, timedelta, timezone

import pytest

from tradingagents.astock.data_sources.quality import DataQualityBanner


class TestDataQualityBanner:
    def test_banner_live(self):
        now = datetime.now(timezone.utc)
        b = DataQualityBanner.banner(source="live", ts=now)
        assert b["source"] == "live"
        assert b["is_mock"] is False
        assert b["is_stale"] is False
        assert b["age_seconds"] == 0

    def test_banner_mock(self):
        b = DataQualityBanner.banner(source="mock", ts=datetime.now(timezone.utc))
        assert b["is_mock"] is True
        assert b["is_stale"] is False

    def test_banner_synthetic(self):
        b = DataQualityBanner.banner(source="synthetic", ts=datetime.now(timezone.utc))
        assert b["is_mock"] is True

    def test_banner_cache_not_stale(self):
        now = datetime.now(timezone.utc)
        b = DataQualityBanner.banner(source="cache", ts=now, ttl_seconds=60)
        assert b["is_stale"] is False

    def test_banner_cache_stale(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=120)
        b = DataQualityBanner.banner(source="cache", ts=past, ttl_seconds=60)
        assert b["is_stale"] is True
        assert b["age_seconds"] > 60

    def test_banner_store_stale(self):
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        b = DataQualityBanner.banner(source="store", ts=past, ttl_seconds=60)
        assert b["is_stale"] is True

    def test_banner_fallback_stale(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=90)
        b = DataQualityBanner.banner(source="fallback", ts=past, ttl_seconds=60)
        assert b["is_stale"] is True

    def test_enrich_preserves_existing(self):
        data = {"symbol": "600519.SH", "last_price": 1800.0}
        enriched = DataQualityBanner.enrich(data, source="live")
        assert enriched["symbol"] == "600519.SH"
        assert enriched["last_price"] == 1800.0
        assert enriched["source"] == "live"
        assert enriched["is_mock"] is False

    def test_enrich_overwrites_conflicting_keys(self):
        data = {"source": "old", "as_of": "2020-01-01"}
        enriched = DataQualityBanner.enrich(data, source="live")
        assert enriched["source"] == "live"

    def test_banner_no_ts_defaults_to_now(self):
        b = DataQualityBanner.banner(source="live")
        assert b["age_seconds"] == 0
        assert b["is_mock"] is False

    def test_banner_naive_datetime(self):
        naive = datetime(2026, 7, 10, 12, 0, 0)
        b = DataQualityBanner.banner(source="live", ts=naive)
        assert b["as_of"] is not None

    def test_banner_ttl_zero_stale(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        b = DataQualityBanner.banner(source="cache", ts=past, ttl_seconds=0)
        assert b["is_stale"] is True

    def test_banner_duckdb_stale(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=90)
        b = DataQualityBanner.banner(source="duckdb", ts=past, ttl_seconds=60)
        assert b["is_stale"] is True
        assert b["is_mock"] is False

    def test_enrich_empty_dict(self):
        enriched = DataQualityBanner.enrich({}, source="live")
        assert enriched["source"] == "live"
        assert enriched["is_mock"] is False
        assert "age_seconds" in enriched

    def test_enrich_none_raises(self):
        with pytest.raises(TypeError):
            DataQualityBanner.enrich(None, source="live")
