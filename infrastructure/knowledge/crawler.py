"""
Web Crawler Infrastructure.

Fetches and extracts content from external sources:
- News APIs, web scraping, RSS feeds
- Rate limiting and retry logic
- Content extraction and normalization
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class CrawlSource(str, Enum):
    NEWS_API = "news_api"
    RSS_FEED = "rss_feed"
    WEB_PAGE = "web_page"
    API_ENDPOINT = "api_endpoint"
    CUSTOM = "custom"


class CrawlStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CrawlJob:
    """A web crawl job definition."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    source: CrawlSource = CrawlSource.WEB_PAGE

    # Headers / auth
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)

    # Content extraction
    extract_title: bool = True
    extract_content: bool = True
    extract_links: bool = False
    max_content_length: int = 50000

    # Scheduling
    priority: int = 0  # higher = more important
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 30.0

    # Metadata
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CrawlResult:
    """Result of a completed crawl job."""

    job_id: str = ""
    url: str = ""
    source: CrawlSource = CrawlSource.WEB_PAGE

    status: CrawlStatus = CrawlStatus.PENDING
    status_code: int = 0
    error_message: str = ""

    # Extracted content
    title: str = ""
    content: str = ""
    links: List[str] = field(default_factory=list)
    raw_html: str = ""

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Metadata
    content_length: int = 0
    content_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "source": self.source.value,
            "status": self.status.value,
            "title": self.title,
            "content_length": self.content_length,
            "duration_ms": self.duration_ms,
            "links": self.links[:10],
        }


@dataclass
class CrawlerConfig:
    """Configuration for the web crawler."""

    # Rate limiting
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    min_delay_between_requests: float = 0.5

    # Content limits
    max_content_length: int = 100000
    max_links_per_page: int = 100

    # Timeouts
    default_timeout: float = 30.0
    max_job_timeout: float = 120.0

    # Retry
    max_retries: int = 3
    retry_backoff: float = 2.0
    retry_on_status_codes: Set[int] = field(default_factory=lambda: {429, 500, 502, 503, 504})

    # User agent
    user_agent: str = "ICYQuant-KnowledgeBot/1.0"

    # Domain filtering
    allowed_domains: Optional[List[str]] = None
    blocked_domains: Optional[List[str]] = None
    respect_robots_txt: bool = True


# ── Web Crawler ──────────────────────────────────────────────────────────────

class WebCrawler:
    """
    Web crawler for fetching alternative data content.

    Simulates web crawling with rate limiting and retry logic.
    Designed to be used with the IngestionPipeline for feeding
    external content into the knowledge platform.
    """

    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self._jobs: Dict[str, CrawlJob] = {}
        self._results: Dict[str, CrawlResult] = {}
        self._request_times: List[float] = []
        self._callbacks: Dict[str, List[Callable]] = {}

    # ── Job Management ───────────────────────────────────────────────────────

    def submit(self, job: CrawlJob) -> str:
        """Submit a crawl job."""
        self._jobs[job.job_id] = job
        return job.job_id

    def submit_url(
        self,
        url: str,
        source: CrawlSource = CrawlSource.WEB_PAGE,
        priority: int = 0,
        **kwargs,
    ) -> str:
        """Submit a simple URL crawl job."""
        job = CrawlJob(
            url=url,
            source=source,
            priority=priority,
            **kwargs,
        )
        return self.submit(job)

    def submit_batch(
        self, urls: List[str], source: CrawlSource = CrawlSource.WEB_PAGE
    ) -> List[str]:
        """Submit multiple URLs in batch."""
        return [self.submit_url(url, source) for url in urls]

    # ── Execution ────────────────────────────────────────────────────────────

    def execute(self, job_id: str) -> CrawlResult:
        """
        Execute a crawl job (simulated).

        In production, this would use httpx/aiohttp for actual HTTP requests.
        """
        job = self._jobs.get(job_id)
        if not job:
            return CrawlResult(
                job_id=job_id,
                status=CrawlStatus.FAILED,
                error_message=f"Job {job_id} not found",
            )

        start = time.time()

        try:
            # Rate limit check
            self._enforce_rate_limit()

            # Simulate fetch (placeholder for actual HTTP logic)
            result = CrawlResult(
                job_id=job.job_id,
                url=job.url,
                source=job.source,
                status=CrawlStatus.COMPLETED,
                status_code=200,
                started_at=datetime.now(timezone.utc),
                title=f"Content from {job.url}",
                content=f"[Simulated content from {job.url}]",
                content_length=len(job.url),
                content_type="text/html",
            )
            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = (time.time() - start) * 1000

        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            result = CrawlResult(
                job_id=job.job_id,
                url=job.url,
                source=job.source,
                status=CrawlStatus.FAILED,
                error_message=str(e),
            )

        # Store result
        self._results[job_id] = result

        # Fire callbacks
        self._fire_callbacks(job_id, result)

        return result

    def execute_all(
        self, max_jobs: Optional[int] = None
    ) -> List[CrawlResult]:
        """Execute all pending jobs."""
        pending = [
            jid for jid, job in self._jobs.items()
            if jid not in self._results
        ]
        results = []
        for jid in pending[:max_jobs or len(pending)]:
            results.append(self.execute(jid))
        return results

    # ── Rate Limiting ────────────────────────────────────────────────────────

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limits between requests."""
        now = time.time()

        # Clean old timestamps
        cutoff = now - 3600
        self._request_times = [t for t in self._request_times if t > cutoff]

        # Check hourly limit
        if len(self._request_times) >= self.config.requests_per_hour:
            oldest = min(self._request_times)
            wait = oldest + 3600 - now
            if wait > 0:
                logger.debug(f"Rate limit: waiting {wait:.1f}s")
                time.sleep(wait)

        # Check per-minute limit
        recent = [t for t in self._request_times if t > now - 60]
        if len(recent) >= self.config.requests_per_minute:
            oldest = min(recent)
            wait = oldest + 60 - now
            if wait > 0:
                logger.debug(f"Rate limit (minute): waiting {wait:.1f}s")
                time.sleep(wait)

        # Minimum delay
        if self._request_times:
            last = max(self._request_times)
            delay = self.config.min_delay_between_requests - (now - last)
            if delay > 0:
                time.sleep(delay)

        self._request_times.append(time.time())

    # ── Callbacks ────────────────────────────────────────────────────────────

    def on_complete(
        self, job_id: str, callback: Callable[[CrawlResult], None]
    ) -> None:
        """Register a completion callback for a job."""
        if job_id not in self._callbacks:
            self._callbacks[job_id] = []
        self._callbacks[job_id].append(callback)

    def _fire_callbacks(self, job_id: str, result: CrawlResult) -> None:
        """Fire all registered callbacks for a job."""
        for cb in self._callbacks.get(job_id, []):
            try:
                cb(result)
            except Exception as e:
                logger.error(f"Callback error for job {job_id}: {e}")

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_result(self, job_id: str) -> Optional[CrawlResult]:
        """Get result for a job."""
        return self._results.get(job_id)

    def get_all_results(self) -> List[CrawlResult]:
        """Get all results."""
        return list(self._results.values())

    def get_job_status(self, job_id: str) -> CrawlStatus:
        """Get job status."""
        result = self._results.get(job_id)
        if result:
            return result.status
        if job_id in self._jobs:
            return CrawlStatus.PENDING
        return CrawlStatus.FAILED

    @property
    def pending_count(self) -> int:
        return len(self._jobs) - len(self._results)

    def clear(self) -> None:
        """Clear all jobs and results."""
        self._jobs.clear()
        self._results.clear()
        self._request_times.clear()
        self._callbacks.clear()
