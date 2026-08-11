"""
System Health — Aggregated health monitoring for the entire autonomous system.

Aggregates health from all domains (Research, Strategy, Portfolio,
Risk, Execution, Data, Infrastructure) into a unified status.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SystemHealth:
    """
    Aggregates health from all autonomous domains into a unified status.

    Each domain contributes a health score. The overall health is the
    minimum across all domains (worst-case drives the status).
    """

    def __init__(self):
        self._domains: dict[str, Any] = {}
        self._domain_scores: dict[str, float] = {}
        self._last_check: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        logger.info("SystemHealth monitor started")

    async def stop(self):
        logger.info("SystemHealth monitor stopped")

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    async def check(self) -> dict:
        """
        Check health of all domains.

        Returns overall status: HEALTHY, WARNING, DEGRADED, or CRITICAL.
        """
        self._last_check = time.time()
        domain_health = {}

        for name, domain in self._domains.items():
            try:
                if hasattr(domain, "check"):
                    health = await domain.check()
                    domain_health[name] = health
                elif hasattr(domain, "health_score"):
                    domain_health[name] = domain.health_score()
            except Exception:
                domain_health[name] = {"status": "UNKNOWN", "error": "check_failed"}

        self._domain_scores = {
            name: self._status_to_score(h.get("status", "UNKNOWN"))
            for name, h in domain_health.items()
        }

        overall = self._compute_overall()
        return {
            "overall": overall,
            "domains": domain_health,
            "timestamp": self._last_check,
        }

    def _status_to_score(self, status: str) -> float:
        mapping = {
            "HEALTHY": 1.0,
            "HEALTHY": 0.9,
            "WARNING": 0.6,
            "DEGRADED": 0.3,
            "CRITICAL": 0.0,
            "UNKNOWN": 0.5,
        }
        return mapping.get(status, 0.0)

    def _compute_overall(self) -> str:
        if not self._domain_scores:
            return "UNKNOWN"

        min_score = min(self._domain_scores.values()) if self._domain_scores else 1.0
        if min_score <= 0.0:
            return "CRITICAL"
        if min_score <= 0.3:
            return "DEGRADED"
        if min_score <= 0.6:
            return "WARNING"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    def register_domain(self, name: str, health_monitor) -> None:
        """Register a domain health monitor."""
        self._domains[name] = health_monitor

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "last_check": self._last_check,
            "domains": len(self._domains),
            "scores": self._domain_scores,
        }
