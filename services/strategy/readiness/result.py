"""Strategy execution readiness result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of a single readiness evaluation.

    ``ready`` is the single source of truth for the signal generation gate:
    a result is only ``ready=True`` when all mandatory checks passed (or when
    only soft gates failed and the strategy policy allows degraded trading).

    The result carries an ``evaluation_id`` (correlating checks, events,
    audit, metrics, signals and orders) plus an optional ``ttl`` so cached
    results expire instead of being reused forever.
    """

    strategy_id: str
    state: str
    ready: bool
    reasons: tuple[str, ...]
    checked_at: float
    evaluation_id: Optional[str] = None
    ttl: Optional[float] = None

    def expired(self, now: float) -> bool:
        """Return True when the result is older than its TTL.

        A result without a TTL never expires on its own.
        """
        if self.ttl is None:
            return False
        return now - self.checked_at > self.ttl
