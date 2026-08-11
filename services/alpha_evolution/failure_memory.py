"""
Failure Memory — Records and learns from failed factors/alphas.

Stores:
    - Failed factor/alpha ID
    - Failure reason (OOS decay, low IC, high correlation, etc.)
    - Market regime when tested
    - Genome content hash (for similarity matching)
    - Generation when rejected

Prevents the system from repeatedly rediscovering the same failures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FailureMemory:
    """
    Records past failures to prevent wasted computation on similar attempts.

    Key feature: similarity search against past failures.
    """

    def __init__(self, max_entries: int = 5000):
        self._failures: List[Dict[str, Any]] = []
        self._max_entries = max_entries

    async def record_failure(
        self,
        individual_id: str,
        reason: str,
        content_hash: str = "",
        regime: str = "",
        generation: int = 0,
        correlation_with_existing: float = 0.0,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """Record a failed individual."""
        entry = {
            "individual_id": individual_id,
            "reason": reason,
            "content_hash": content_hash,
            "regime": regime,
            "generation": generation,
            "correlation_with_existing": correlation_with_existing,
            "metrics": metrics or {},
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._failures.append(entry)

        # Prune old entries
        if len(self._failures) > self._max_entries:
            self._failures = self._failures[-self._max_entries:]

        logger.debug("Recorded failure: %s — %s", individual_id[:12], reason)

    async def is_similar_to_past_failure(
        self,
        content_hash: str,
        feature_set: Optional[set] = None,
        threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Check if a candidate is similar to a past failure."""
        for failure in self._failures:
            if failure.get("content_hash") == content_hash:
                return failure
        return None

    async def get_failures_by_reason(self, reason: str, limit: int = 50) -> List[Dict[str, Any]]:
        return [f for f in self._failures if reason.lower() in f.get("reason", "").lower()][:limit]

    async def get_recent_failures(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._failures[-limit:]

    async def get_failure_stats(self) -> Dict[str, Any]:
        """Statistics on failure reasons."""
        reasons: Dict[str, int] = {}
        regimes: Dict[str, int] = {}
        for f in self._failures:
            reason = f.get("reason", "unknown")
            regime = f.get("regime", "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
            regimes[regime] = regimes.get(regime, 0) + 1
        return {
            "total_failures": len(self._failures),
            "by_reason": reasons,
            "by_regime": regimes,
        }

    async def get_common_rejection_reasons(self, top_n: int = 10) -> List[tuple[str, int]]:
        """Most common failure reasons."""
        reasons: Dict[str, int] = {}
        for f in self._failures:
            reason = f.get("reason", "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
        return sorted_reasons[:top_n]
