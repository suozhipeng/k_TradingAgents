"""
Data quality metadata — tags and schema for data source quality assessment.

Phase 31 additions
------------------
- ``DataQualityTag`` enum — standardised quality levels for data sources.
- ``FreshnessInfo`` — freshness metadata (age, staleness threshold).
- ``DataQualityMetadata`` — combined quality + freshness + fallback info.

Every data API response should carry a ``DataQualityMetadata`` in its
``meta`` block so the frontend can display data quality indicators.

Quality levels
--------------
``normal``     Data is current, complete, and from a primary source.
``stale``      Data is older than the acceptable freshness threshold.
``partial``    Data set is incomplete (e.g. missing symbols or date range).
``fallback``   Data sourced from a secondary/fallback provider.
``mock``       Data is synthetic / test-only, not from a real provider.
``degraded``   Provider responded but with errors, timeouts, or reduced payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from tradingagents.astock.time_utils import utc_now
from typing import Any, Optional


class DataQualityTag(str, Enum):
    """Quality level of a data source response.

    Enum values are lowercase strings suitable for JSON serialisation.
    """

    NORMAL = "normal"
    STALE = "stale"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    MOCK = "mock"
    DEGRADED = "degraded"

    @property
    def display_name(self) -> str:
        """Human-readable Chinese label."""
        labels = {
            "normal": "正常",
            "stale": "过期",
            "partial": "不完整",
            "fallback": "降级",
            "mock": "模拟",
            "degraded": "异常",
        }
        return labels.get(self.value, self.value)

    @property
    def is_warning(self) -> bool:
        """Whether this tag should trigger a warning indicator in the UI."""
        return self in (DataQualityTag.STALE, DataQualityTag.PARTIAL, DataQualityTag.DEGRADED)

    @property
    def is_error(self) -> bool:
        """Whether this tag indicates functional unavailability."""
        return self is DataQualityTag.DEGRADED

    @classmethod
    def from_age(
        cls,
        generated_at: datetime | str | None,
        *,
        stale_after: timedelta = timedelta(hours=4),
        degraded_after: timedelta = timedelta(days=1),
    ) -> DataQualityTag:
        """Determine quality tag based on data age.

        Parameters
        ----------
        generated_at : datetime or str or None
            When the data was generated. ``None`` means no timestamp.
        stale_after : timedelta
            Age after which data is considered stale (default 4 hours).
        degraded_after : timedelta
            Age after which data is considered degraded (default 1 day).

        Returns
        -------
        DataQualityTag
        """
        if generated_at is None:
            return DataQualityTag.DEGRADED

        if isinstance(generated_at, str):
            try:
                generated_at = datetime.fromisoformat(generated_at)
            except (ValueError, TypeError):
                return DataQualityTag.DEGRADED

        age = utc_now() - generated_at
        if age > degraded_after:
            return DataQualityTag.DEGRADED
        if age > stale_after:
            return DataQualityTag.STALE
        return DataQualityTag.NORMAL


@dataclass
class FreshnessInfo:
    """Freshness metadata for a data response.

    Attributes
    ----------
    generated_at : str or None
        ISO-8601 timestamp of data generation.
    age_seconds : float or None
        Age of the data in seconds (computed on construction).
    stale_threshold_seconds : float
        Threshold in seconds after which data is considered stale (default 14400 = 4h).
    tag : DataQualityTag
        Computed quality tag based on age.
    """

    generated_at: Optional[str] = None
    age_seconds: Optional[float] = None
    stale_threshold_seconds: float = 14_400  # 4 hours
    tag: DataQualityTag = DataQualityTag.NORMAL

    @classmethod
    def from_generated_at(
        cls,
        generated_at: str | None,
        *,
        stale_after_seconds: float = 14_400,
        degraded_after_seconds: float = 86_400,
    ) -> FreshnessInfo:
        """Construct from an ISO timestamp string.

        Parameters
        ----------
        generated_at : str or None
            ISO-8601 timestamp.
        stale_after_seconds : float
            Seconds after which data is stale.
        degraded_after_seconds : float
            Seconds after which data is degraded.

        Returns
        -------
        FreshnessInfo
        """
        if generated_at is None:
            return cls(
                generated_at=None,
                age_seconds=None,
                stale_threshold_seconds=stale_after_seconds,
                tag=DataQualityTag.DEGRADED,
            )

        try:
            dt = datetime.fromisoformat(generated_at)
            age = (utc_now() - dt).total_seconds()
        except (ValueError, TypeError):
            return cls(
                generated_at=generated_at,
                age_seconds=None,
                stale_threshold_seconds=stale_after_seconds,
                tag=DataQualityTag.DEGRADED,
            )

        if age > degraded_after_seconds:
            tag = DataQualityTag.DEGRADED
        elif age > stale_after_seconds:
            tag = DataQualityTag.STALE
        else:
            tag = DataQualityTag.NORMAL

        return cls(
            generated_at=generated_at,
            age_seconds=round(age, 1),
            stale_threshold_seconds=stale_after_seconds,
            tag=tag,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "age_seconds": self.age_seconds,
            "stale_threshold_seconds": self.stale_threshold_seconds,
            "freshness": self.tag.value,
        }


@dataclass
class DataQualityMetadata:
    """Combined quality, freshness, and fallback info for a data API response.

    Intended for inclusion in API response ``meta`` blocks.

    Attributes
    ----------
    tag : DataQualityTag
        Overall data quality tag.
    freshness : FreshnessInfo
        Freshness information.
    source : str
        Primary data source name (e.g. ``"duckdb"``, ``"eastmoney"``).
    fallback_source : str or None
        Fallback source used, if any.
    fallback_path : list[str]
        Ordered list of sources tried before reaching the final source.
    cache_hit : bool
        Whether the response was served from cache.
    """

    tag: DataQualityTag = DataQualityTag.NORMAL
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)
    source: str = "unknown"
    fallback_source: str | None = None
    fallback_path: list[str] = field(default_factory=list)
    cache_hit: bool = False
    capability: str = "research"

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "source": self.source,
            "quality": self.tag.value,
            "freshness": self.freshness.to_dict(),
            "fallback_source": self.fallback_source,
            "fallback_path": list(self.fallback_path),
            "cache_hit": self.cache_hit,
        }

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        tag: DataQualityTag | None = None,
        generated_at: str | None = None,
        fallback_source: str | None = None,
        fallback_path: list[str] | None = None,
        cache_hit: bool = False,
        capability: str = "research",
    ) -> DataQualityMetadata:
        """Convenience constructor from source name and optional freshness.

        Parameters
        ----------
        source : str
            Primary data source.
        tag : DataQualityTag or None
            Explicit quality tag. Auto-computed from freshness if ``None``.
        generated_at : str or None
            ISO timestamp for freshness computation.
        fallback_source : str or None
            Fallback source, if any.
        fallback_path : list[str] or None
            Full fallback path.
        cache_hit : bool
            Whether cached.
        capability : str
            Capability level.

        Returns
        -------
        DataQualityMetadata
        """
        if tag:
            quality_tag = tag
        elif generated_at:
            freshness_info = FreshnessInfo.from_generated_at(generated_at)
            quality_tag = freshness_info.tag
        else:
            quality_tag = DataQualityTag.NORMAL

        freshness_info = (
            FreshnessInfo.from_generated_at(generated_at)
            if generated_at
            else FreshnessInfo(tag=quality_tag)
        )

        return cls(
            tag=quality_tag,
            freshness=freshness_info,
            source=source,
            fallback_source=fallback_source,
            fallback_path=fallback_path or [],
            cache_hit=cache_hit,
            capability=capability,
        )


class DataQualityBanner:
    """Inject data quality fields into API responses.

    Provides ``banner()`` and ``enrich()`` helpers that inject
    *source*, *as_of*, *age_seconds*, *is_mock*, and *is_stale* into
    API responses.
    """

    _MOCK_SOURCES = frozenset({"mock", "synthetic"})
    _STALE_SOURCES = frozenset({"cache", "store", "fallback", "duckdb"})

    @classmethod
    def banner(
        cls,
        *,
        source: str,
        ts: datetime | None = None,
        ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        """Build a quality banner dict.

        Parameters
        ----------
        source : str
            Data source identifier (e.g. ``"live"``, ``"mock"``, ``"cache"``).
        ts : datetime or None
            Timestamp of the data.  Defaults to current UTC time.
        ttl_seconds : int
            Staleness threshold in seconds (default 60).

        Returns
        -------
        dict[str, Any]
            Banner dict with *source*, *as_of*, *age_seconds*, *is_mock*, *is_stale*.
        """
        if ts is None:
            ts = datetime.now(timezone.utc)

        if ts.tzinfo is None:
            ts_utc = ts.replace(tzinfo=timezone.utc)
        else:
            ts_utc = ts.astimezone(timezone.utc)

        now_utc = datetime.now(timezone.utc)
        age_seconds = max(0, int((now_utc - ts_utc).total_seconds()))
        as_of = ts_utc.isoformat()

        is_mock = source in cls._MOCK_SOURCES
        is_stale = source in cls._STALE_SOURCES and age_seconds > ttl_seconds

        return {
            "source": source,
            "as_of": as_of,
            "age_seconds": age_seconds,
            "is_mock": is_mock,
            "is_stale": is_stale,
        }

    @classmethod
    def enrich(
        cls,
        data: dict[str, Any],
        *,
        source: str,
        ts: datetime | None = None,
        ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        """Enrich an existing dict with quality banner fields.

        Parameters
        ----------
        data : dict[str, Any]
            Existing data dictionary.
        source : str
            Data source identifier.
        ts : datetime or None
            Timestamp of the data.
        ttl_seconds : int
            Staleness threshold in seconds.

        Returns
        -------
        dict[str, Any]
            New dict with quality banner fields injected.
        """
        banner = cls.banner(source=source, ts=ts, ttl_seconds=ttl_seconds)
        result = dict(data)
        result.update(banner)
        return result


__all__ = [
    "DataQualityTag",
    "FreshnessInfo",
    "DataQualityMetadata",
    "DataQualityBanner",
]
