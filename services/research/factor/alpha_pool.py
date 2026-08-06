"""Alpha Pool — unified alpha factor lifecycle management.

Lifecycle::

    Candidate → Validated → Production → Deprecated

Manages the full alpha factor lifecycle from discovery to retirement.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .factor_repository import FactorRepository

logger = logging.getLogger(__name__)


class AlphaState(str, Enum):
    """Alpha factor lifecycle states."""

    CANDIDATE = "candidate"       # Newly discovered, under review
    VALIDATED = "validated"       # Passed quality thresholds
    PRODUCTION = "production"     # Live in production
    PAUSED = "paused"             # Temporarily suspended
    DEPRECATED = "deprecated"     # Retired, no longer used
    REJECTED = "rejected"         # Failed validation


@dataclass
class AlphaEntry:
    """A single alpha factor entry in the pool."""

    id: str
    factor_id: str
    factor_name: str
    status: AlphaState = AlphaState.CANDIDATE
    ic_mean: float = 0.0
    icir: float = 0.0
    rank_ic: float = 0.0
    decay_half_life: Optional[int] = None
    avg_turnover: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    capacity: float = 0.0  # AUM capacity estimate
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    promoted_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "factor_id": self.factor_id,
            "factor_name": self.factor_name,
            "status": self.status.value,
            "ic_mean": self.ic_mean,
            "icir": self.icir,
            "rank_ic": self.rank_ic,
            "decay_half_life": self.decay_half_life,
            "avg_turnover": self.avg_turnover,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "capacity": self.capacity,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AlphaPool:
    """Unified alpha factor pool with lifecycle management.

    Responsibilities:
    * Accept candidate factors
    * Validate against quality thresholds
    * Promote validated factors to production
    * Monitor production factor performance
    * Deprecate underperforming factors
    * Maintain full audit trail

    Lifecycle::

        Candidate → Validated → Production → Deprecated
           │            │
           └── Rejected ┘
    """

    # Quality thresholds
    MIN_IC = 0.02
    MIN_ICIR = 0.3
    MIN_RANK_IC = 0.02
    MAX_TURNOVER = 0.5
    MIN_HALF_LIFE = 5

    def __init__(
        self,
        repository: Optional[FactorRepository] = None,
    ) -> None:
        self._repository = repository or FactorRepository()
        self._entries: Dict[str, AlphaEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "candidate": 0,
            "validated": 0,
            "production": 0,
            "deprecated": 0,
            "rejected": 0,
            "total_submitted": 0,
        }

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    async def submit(
        self,
        factor: Dict[str, Any],
        min_ic_threshold: float = 0.02,
        min_icir_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """Submit a factor to the alpha pool.

        The factor is first registered as a candidate, then validated
        against quality thresholds. If it passes, it's promoted to
        validated status.
        """
        async with self._lock:
            self._stats["total_submitted"] += 1
            factor_id = factor.get("id", "")

            # Create alpha entry
            entry = AlphaEntry(
                id=factor_id,
                factor_id=factor_id,
                factor_name=factor.get("name", ""),
                status=AlphaState.CANDIDATE,
                ic_mean=factor.get("ic_mean", 0.0),
                icir=factor.get("icir", 0.0),
                rank_ic=factor.get("rank_ic", 0.0),
                tags=factor.get("tags", []),
                metadata=factor.get("metadata", {}),
            )

            # Validate against thresholds
            validation_result = self._validate(entry, min_ic_threshold, min_icir_threshold)

            if validation_result["passed"]:
                entry.status = AlphaState.VALIDATED
                entry.promoted_at = datetime.now(timezone.utc)
                self._stats["validated"] += 1
                logger.info("Factor %s validated in Alpha Pool", factor_id)
            else:
                entry.status = AlphaState.REJECTED
                self._stats["rejected"] += 1
                logger.info(
                    "Factor %s rejected from Alpha Pool: %s",
                    factor_id, validation_result["reason"],
                )

            self._entries[factor_id] = entry
            self._stats["candidate"] += 1

            # Persist to repository
            await self._repository.create_alpha_entry(entry.to_dict())

            return {
                "factor_id": factor_id,
                "status": entry.status.value,
                "validation": validation_result,
                "entry": entry.to_dict(),
            }

    def _validate(
        self,
        entry: AlphaEntry,
        min_ic_threshold: float,
        min_icir_threshold: float,
    ) -> Dict[str, Any]:
        """Validate factor against quality thresholds."""
        checks = []

        # IC check
        ic_ok = abs(entry.ic_mean) >= min_ic_threshold
        checks.append({
            "check": "ic",
            "passed": ic_ok,
            "value": entry.ic_mean,
            "threshold": min_ic_threshold,
        })

        # ICIR check
        icir_ok = abs(entry.icir) >= min_icir_threshold
        checks.append({
            "check": "icir",
            "passed": icir_ok,
            "value": entry.icir,
            "threshold": min_icir_threshold,
        })

        # RankIC check
        rankic_ok = abs(entry.rank_ic) >= self.MIN_RANK_IC
        checks.append({
            "check": "rank_ic",
            "passed": rankic_ok,
            "value": entry.rank_ic,
            "threshold": self.MIN_RANK_IC,
        })

        # Turnover check (if available)
        if entry.avg_turnover > 0:
            turnover_ok = entry.avg_turnover <= self.MAX_TURNOVER
            checks.append({
                "check": "turnover",
                "passed": turnover_ok,
                "value": entry.avg_turnover,
                "threshold": self.MAX_TURNOVER,
            })

        # Half-life check (if available)
        if entry.decay_half_life is not None:
            hl_ok = entry.decay_half_life >= self.MIN_HALF_LIFE
            checks.append({
                "check": "half_life",
                "passed": hl_ok,
                "value": entry.decay_half_life,
                "threshold": self.MIN_HALF_LIFE,
            })

        passed = all(c["passed"] for c in checks)
        failed_checks = [c["check"] for c in checks if not c["passed"]]

        return {
            "passed": passed,
            "checks": checks,
            "reason": f"Failed: {', '.join(failed_checks)}" if failed_checks else "All checks passed",
        }

    async def promote(self, factor_id: str) -> Dict[str, Any]:
        """Promote a validated factor to production."""
        async with self._lock:
            entry = self._entries.get(factor_id)
            if entry is None:
                raise ValueError(f"Factor not in alpha pool: {factor_id}")
            if entry.status != AlphaState.VALIDATED:
                raise ValueError(f"Factor not in validated state: {entry.status.value}")

            entry.status = AlphaState.PRODUCTION
            entry.promoted_at = datetime.now(timezone.utc)
            self._stats["production"] += 1
            self._stats["validated"] -= 1

            await self._repository.update_alpha_entry(factor_id, {
                "status": AlphaState.PRODUCTION.value,
            })

            logger.info("Factor %s promoted to production", factor_id)
            return {"factor_id": factor_id, "status": entry.status.value}

    async def deprecate(self, factor_id: str, reason: str = "") -> Dict[str, Any]:
        """Deprecate a factor from the pool."""
        async with self._lock:
            entry = self._entries.get(factor_id)
            if entry is None:
                raise ValueError(f"Factor not in alpha pool: {factor_id}")

            old_status = entry.status.value
            entry.status = AlphaState.DEPRECATED
            entry.deprecated_at = datetime.now(timezone.utc)
            entry.metadata["deprecation_reason"] = reason

            self._stats["deprecated"] += 1
            if old_status == AlphaState.PRODUCTION.value:
                self._stats["production"] -= 1
            elif old_status == AlphaState.VALIDATED.value:
                self._stats["validated"] -= 1

            await self._repository.update_alpha_entry(factor_id, {
                "status": AlphaState.DEPRECATED.value,
            })

            logger.info("Factor %s deprecated: %s", factor_id, reason)
            return {"factor_id": factor_id, "status": entry.status.value, "reason": reason}

    async def get(self, factor_id: str) -> Optional[AlphaEntry]:
        return self._entries.get(factor_id)

    async def list_by_status(self, status: AlphaState) -> List[AlphaEntry]:
        return [e for e in self._entries.values() if e.status == status]

    async def list_all(self) -> List[AlphaEntry]:
        return list(self._entries.values())

    async def top_factors(self, n: int = 10) -> List[AlphaEntry]:
        """Get top N factors by ICIR."""
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: abs(e.icir),
            reverse=True,
        )
        return sorted_entries[:n]

    async def summary(self) -> Dict[str, Any]:
        """Generate alpha pool summary."""
        all_entries = await self.list_all()
        production = [e for e in all_entries if e.status == AlphaState.PRODUCTION]
        validated = [e for e in all_entries if e.status == AlphaState.VALIDATED]

        return {
            "total_factors": len(all_entries),
            "production_count": len(production),
            "validated_count": len(validated),
            "candidate_count": len([e for e in all_entries if e.status == AlphaState.CANDIDATE]),
            "deprecated_count": len([e for e in all_entries if e.status == AlphaState.DEPRECATED]),
            "avg_icir": sum(e.icir for e in production) / len(production) if production else 0.0,
            "avg_ic": sum(e.ic_mean for e in production) / len(production) if production else 0.0,
            "top_factor": production[0].factor_name if production else None,
            "stats": self._stats,
        }
