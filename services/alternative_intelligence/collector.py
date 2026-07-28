"""Alternative Data Collector — ingests and normalizes data from diverse alternative sources."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeRecord,
    DataSource,
    NewsArticle,
    SatelliteObservation,
    SocialPost,
    WebMetric,
)


@dataclass
class CollectorStats:
    """Statistics about collected data."""

    total_records: int = 0
    records_by_source: dict[str, int] = field(default_factory=dict)
    records_by_asset: dict[str, int] = field(default_factory=dict)
    last_collection_time: str = ""
    errors: list[str] = field(default_factory=list)


class AlternativeDataCollector:
    """Collects and normalizes data from alternative sources.

    Supports: news, social media, web metrics, satellite observations,
    supply chain, hiring data, app data, consumer data, geolocation, credit card.
    """

    def __init__(self) -> None:
        self._records: list[AlternativeRecord] = []
        self._stats = CollectorStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, source: str) -> list[AlternativeRecord]:
        """Collect all records from a specific source.

        Returns records matching the given source name.
        """
        return [r for r in self._records if r.source.lower() == source.lower()]

    def ingest_raw(
        self,
        source: str,
        content: str,
        asset_tags: list[str] | None = None,
        metadata: dict | None = None,
        confidence: float = 0.5,
    ) -> AlternativeRecord:
        """Ingest a raw alternative data record."""
        record = AlternativeRecord(
            source=source,
            content=content,
            asset_tags=asset_tags or [],
            metadata=metadata or {},
            confidence=min(max(confidence, 0.0), 1.0),
        )
        self._records.append(record)
        self._stats.total_records += 1
        self._stats.records_by_source[source] = (
            self._stats.records_by_source.get(source, 0) + 1
        )
        for tag in record.asset_tags:
            self._stats.records_by_asset[tag] = (
                self._stats.records_by_asset.get(tag, 0) + 1
            )
        return record

    def ingest_news(self, article: NewsArticle) -> AlternativeRecord:
        """Ingest a structured news article."""
        return self.ingest_raw(
            source=DataSource.NEWS.value,
            content=f"{article.headline}\n{article.body}",
            asset_tags=article.asset_tags,
            metadata={
                "headline": article.headline,
                "source_name": article.source_name,
                "author": article.author,
                "url": article.url,
                "category": article.category,
                "language": article.language,
                "published_at": article.published_at,
            },
            confidence=0.7,  # news articles have moderate default confidence
        )

    def ingest_social_post(self, post: SocialPost) -> AlternativeRecord:
        """Ingest a structured social media post."""
        return self.ingest_raw(
            source=DataSource.SOCIAL_MEDIA.value,
            content=post.content,
            asset_tags=post.asset_tags,
            metadata={
                "platform": post.platform,
                "author": post.author,
                "posted_at": post.posted_at,
                "followers_count": post.followers_count,
                "engagement": post.engagement,
            },
            confidence=0.4,  # social media has lower default confidence
        )

    def ingest_web_metric(self, metric: WebMetric) -> AlternativeRecord:
        """Ingest a web intelligence metric."""
        return self.ingest_raw(
            source=DataSource.WEB_DATA.value,
            content=f"{metric.metric_type}: {metric.value} ({metric.change_pct:+.1f}%)",
            asset_tags=metric.asset_tags,
            metadata={
                "metric_type": metric.metric_type,
                "value": metric.value,
                "change_pct": metric.change_pct,
                "period": metric.period,
                "source_url": metric.source_url,
            },
            confidence=0.6,
        )

    def ingest_satellite_observation(
        self, observation: SatelliteObservation
    ) -> AlternativeRecord:
        """Ingest a satellite-derived observation."""
        return self.ingest_raw(
            source=DataSource.SATELLITE.value,
            content=(
                f"{observation.observation_type} at {observation.location}: "
                f"activity={observation.activity_score:.0f} "
                f"(Δ{observation.change_pct:+.1f}%)"
            ),
            asset_tags=observation.asset_tags,
            metadata={
                "location": observation.location,
                "observation_type": observation.observation_type,
                "activity_score": observation.activity_score,
                "change_pct": observation.change_pct,
                "coordinates": observation.coordinates,
                "observed_at": observation.observed_at,
            },
            confidence=0.65,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_by_asset(self, asset_tag: str) -> list[AlternativeRecord]:
        """Get all records associated with a specific asset."""
        return [r for r in self._records if asset_tag in r.asset_tags]

    def get_by_source(self, source: str) -> list[AlternativeRecord]:
        """Get all records from a specific source type."""
        return [r for r in self._records if r.source.lower() == source.lower()]

    def get_recent(self, limit: int = 100) -> list[AlternativeRecord]:
        """Get the most recent records."""
        return self._records[-limit:]

    def get_source_summary(self) -> dict[str, int]:
        """Get a summary of records per source type."""
        summary: dict[str, int] = defaultdict(int)
        for r in self._records:
            summary[r.source] += 1
        return dict(summary)

    def get_asset_summary(self) -> dict[str, int]:
        """Get a summary of records per asset tag."""
        summary: dict[str, int] = defaultdict(int)
        for r in self._records:
            for tag in r.asset_tags:
                summary[tag] += 1
        return dict(summary)

    @property
    def stats(self) -> CollectorStats:
        """Get collection statistics."""
        return self._stats

    @property
    def record_count(self) -> int:
        """Total number of ingested records."""
        return len(self._records)

    def clear(self) -> None:
        """Clear all collected records and reset stats."""
        self._records.clear()
        self._stats = CollectorStats()
