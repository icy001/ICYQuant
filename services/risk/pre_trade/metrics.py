"""
Pre-Trade Metrics — Prometheus-compatible metrics for the Pre-Trade Risk Platform.

Exposes operational metrics for monitoring, alerting, and dashboarding:

- icyquant_pretrade_requests_total
- icyquant_pretrade_approved_total
- icyquant_pretrade_rejected_total
- icyquant_pretrade_latency
- icyquant_pretrade_rule_hits
- icyquant_margin_check_failures
- icyquant_rate_limit_blocks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PreTradeMetrics:
    """
    Internal metrics collector for the Pre-Trade Risk Platform.

    Tracks request counts, approval/rejection rates, latency
    distributions, rule hit rates, and specific failure modes.
    Designed to be compatible with Prometheus push/pull patterns.

    Usage::

        metrics = PreTradeMetrics()
        metrics.record_request()
        metrics.record_approved()
        metrics.record_latency(2.5)
        snapshot = metrics.snapshot()
    """

    # ---- Counters ----
    requests_total: int = 0
    approved_total: int = 0
    rejected_total: int = 0
    escalated_total: int = 0
    pending_review_total: int = 0
    errors_total: int = 0

    # ---- Rule Hits ----
    rule_hits: dict[str, int] = field(default_factory=dict)

    # ---- Failure Counters ----
    margin_check_failures: int = 0
    rate_limit_blocks: int = 0
    position_limit_blocks: int = 0
    exposure_limit_blocks: int = 0
    buying_power_failures: int = 0
    cash_failures: int = 0
    liquidity_failures: int = 0
    compliance_blocks: int = 0
    instrument_permission_blocks: int = 0

    # ---- Latency (ms) ----
    latency_samples: list[float] = field(default_factory=list)
    latency_sum_ms: float = 0.0
    latency_min_ms: float = float("inf")
    latency_max_ms: float = 0.0
    latency_max_samples: int = 10_000

    # ---- Runtime ----
    last_updated: Optional[datetime] = None

    # ---- Record Methods ----

    def record_request(self) -> None:
        """Record an incoming pre-trade request."""
        self.requests_total += 1
        self._touch()

    def record_approved(self) -> None:
        """Record an approved decision."""
        self.approved_total += 1
        self._touch()

    def record_rejected(self) -> None:
        """Record a rejected decision."""
        self.rejected_total += 1
        self._touch()

    def record_escalated(self) -> None:
        """Record an escalated decision."""
        self.escalated_total += 1
        self._touch()

    def record_pending_review(self) -> None:
        """Record a pending review decision."""
        self.pending_review_total += 1
        self._touch()

    def record_error(self) -> None:
        """Record an evaluation error."""
        self.errors_total += 1
        self._touch()

    def record_rule_hit(self, rule_name: str, count: int = 1) -> None:
        """Record a rule trigger."""
        self.rule_hits[rule_name] = self.rule_hits.get(rule_name, 0) + count
        self._touch()

    def record_latency(self, latency_ms: float) -> None:
        """Record evaluation latency in milliseconds."""
        self.latency_sum_ms += latency_ms
        if latency_ms < self.latency_min_ms:
            self.latency_min_ms = latency_ms
        if latency_ms > self.latency_max_ms:
            self.latency_max_ms = latency_ms

        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > self.latency_max_samples:
            self.latency_samples = self.latency_samples[-self.latency_max_samples:]

        self._touch()

    def record_margin_failure(self) -> None:
        """Record a margin check failure."""
        self.margin_check_failures += 1
        self._touch()

    def record_rate_limit_block(self) -> None:
        """Record a rate limit block."""
        self.rate_limit_blocks += 1
        self._touch()

    def record_position_limit_block(self) -> None:
        """Record a position limit block."""
        self.position_limit_blocks += 1
        self._touch()

    def record_exposure_limit_block(self) -> None:
        """Record an exposure limit block."""
        self.exposure_limit_blocks += 1
        self._touch()

    def record_buying_power_failure(self) -> None:
        """Record a buying power failure."""
        self.buying_power_failures += 1
        self._touch()

    def record_cash_failure(self) -> None:
        """Record a cash check failure."""
        self.cash_failures += 1
        self._touch()

    def record_liquidity_failure(self) -> None:
        """Record a liquidity check failure."""
        self.liquidity_failures += 1
        self._touch()

    def record_compliance_block(self) -> None:
        """Record a compliance block."""
        self.compliance_blocks += 1
        self._touch()

    def record_instrument_permission_block(self) -> None:
        """Record an instrument permission block."""
        self.instrument_permission_blocks += 1
        self._touch()

    # ---- Query ----

    @property
    def approval_rate(self) -> float:
        """Overall approval rate (0.0–1.0)."""
        if self.requests_total == 0:
            return 1.0
        return self.approved_total / self.requests_total

    @property
    def rejection_rate(self) -> float:
        """Overall rejection rate (0.0–1.0)."""
        if self.requests_total == 0:
            return 0.0
        return self.rejected_total / self.requests_total

    @property
    def avg_latency_ms(self) -> float:
        """Average evaluation latency in milliseconds."""
        total = len(self.latency_samples) or 1
        return self.latency_sum_ms / total

    def snapshot(self) -> dict[str, Any]:
        """Return a full metrics snapshot for Prometheus."""
        self._touch()
        return {
            "icyquant_pretrade_requests_total": self.requests_total,
            "icyquant_pretrade_approved_total": self.approved_total,
            "icyquant_pretrade_rejected_total": self.rejected_total,
            "icyquant_pretrade_escalated_total": self.escalated_total,
            "icyquant_pretrade_pending_review_total": self.pending_review_total,
            "icyquant_pretrade_errors_total": self.errors_total,
            "icyquant_pretrade_rule_hits": dict(self.rule_hits),
            "icyquant_margin_check_failures": self.margin_check_failures,
            "icyquant_rate_limit_blocks": self.rate_limit_blocks,
            "icyquant_position_limit_blocks": self.position_limit_blocks,
            "icyquant_exposure_limit_blocks": self.exposure_limit_blocks,
            "icyquant_buying_power_failures": self.buying_power_failures,
            "icyquant_cash_failures": self.cash_failures,
            "icyquant_liquidity_failures": self.liquidity_failures,
            "icyquant_compliance_blocks": self.compliance_blocks,
            "icyquant_instrument_permission_blocks": self.instrument_permission_blocks,
            "icyquant_pretrade_latency_avg_ms": self.avg_latency_ms,
            "icyquant_pretrade_latency_min_ms": (
                self.latency_min_ms if self.latency_samples else 0.0
            ),
            "icyquant_pretrade_latency_max_ms": self.latency_max_ms,
            "icyquant_pretrade_approval_rate": self.approval_rate,
            "icyquant_pretrade_rejection_rate": self.rejection_rate,
        }

    def _touch(self) -> None:
        """Update timestamp."""
        self.last_updated = datetime.now(timezone.utc)
