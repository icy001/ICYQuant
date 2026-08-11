"""
Strategy Audit Center — Comprehensive audit logging and compliance.

Records all strategy platform operations for regulatory compliance,
forensic analysis, and operational transparency.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditCategory(str, Enum):
    """Audit record categories."""
    # Platform
    PLATFORM = "platform"
    PLATFORM_START = "platform.start"
    PLATFORM_STOP = "platform.stop"

    # Strategy
    STRATEGY_REGISTER = "strategy.register"
    STRATEGY_DEPLOY = "strategy.deploy"
    STRATEGY_LIFECYCLE = "strategy.lifecycle"
    STRATEGY_ROLLBACK = "strategy.rollback"

    # Deployment
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    CANARY = "canary"
    ROLLOUT = "rollout"

    # Signal & Decision
    SIGNAL = "strategy.signal"
    DECISION = "strategy.decision"
    ORDER_INTENT = "strategy.order_intent"

    # Order & Execution
    ORDER = "strategy.order"
    EXECUTION = "strategy.execution"

    # Risk
    RISK = "strategy.risk"
    KILL_SWITCH = "strategy.kill_switch"

    # Configuration
    CONFIG = "strategy.config"
    CONFIG_CHANGE = "strategy.config.change"

    # Access
    ACCESS = "strategy.access"
    API = "strategy.api"


class AuditLevel(str, Enum):
    """Audit severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditRecord:
    """A single audit record."""
    record_id: str
    category: AuditCategory
    level: AuditLevel = AuditLevel.INFO
    message: str = ""
    strategy_id: Optional[str] = None
    user_id: Optional[str] = None
    source: str = "strategy_platform"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    request_id: Optional[str] = None


class AuditCenter:
    """
    Central audit logging for strategy platform operations.

    Records all significant platform events for compliance,
    forensic analysis, and operational monitoring with full
    traceability.

    Usage::

        audit = AuditCenter()
        await audit.initialize()
        await audit.record(
            category=AuditCategory.STRATEGY_DEPLOY,
            message="Strategy deployed to production",
            strategy_id="strat_001",
            level=AuditLevel.INFO,
        )
        records = await audit.query(strategy_id="strat_001")
    """

    def __init__(self, max_records: int = 100000) -> None:
        self._records: list[AuditRecord] = []
        self._counter: int = 0
        self._max_records = max_records
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the audit center."""
        self._initialized = True
        logger.info("AuditCenter initialized.")

    async def stop(self) -> None:
        """Stop the audit center."""
        self._initialized = False
        logger.info("AuditCenter stopped.")

    # ---- Recording ----

    async def record(
        self,
        category: AuditCategory | str,
        message: str,
        strategy_id: Optional[str] = None,
        level: AuditLevel = AuditLevel.INFO,
        user_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> AuditRecord:
        """Record an audit event."""
        async with self._lock:
            self._counter += 1
            record_id = f"audit_{self._counter:08d}"

            if isinstance(category, str):
                try:
                    category = AuditCategory(category)
                except ValueError:
                    pass

            record = AuditRecord(
                record_id=record_id,
                category=category if isinstance(category, AuditCategory) else AuditCategory.PLATFORM,
                level=level,
                message=message,
                strategy_id=strategy_id,
                user_id=user_id,
                details=details or {},
                **kwargs,
            )
            self._records.append(record)

            # Trim if over limit
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

        logger.info(f"Audit: [{level.value}] [{category}] {message}")
        return record

    async def record_batch(self, records: list[tuple[AuditCategory, str]]) -> list[AuditRecord]:
        """Record multiple audit events."""
        results = []
        for category, message in records:
            result = await self.record(category=category, message=message)
            results.append(result)
        return results

    # ---- Querying ----

    async def query(
        self,
        strategy_id: Optional[str] = None,
        category: Optional[AuditCategory] = None,
        level: Optional[AuditLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Query audit records with filters."""
        results = self._records

        if strategy_id:
            results = [r for r in results if r.strategy_id == strategy_id]
        if category:
            results = [r for r in results if r.category == category]
        if level:
            results = [r for r in results if r.level == level]
        if start_time:
            results = [r for r in results if r.timestamp >= start_time]
        if end_time:
            results = [r for r in results if r.timestamp <= end_time]

        return sorted(results, key=lambda r: r.timestamp, reverse=True)[:limit]

    async def get_record(self, record_id: str) -> Optional[AuditRecord]:
        """Get a specific audit record by ID."""
        for record in self._records:
            if record.record_id == record_id:
                return record
        return None

    async def get_recent(self, limit: int = 100) -> list[AuditRecord]:
        """Get the most recent audit records."""
        return self._records[-limit:][::-1]

    async def get_strategy_audit_trail(
        self,
        strategy_id: str,
        limit: int = 500,
    ) -> list[AuditRecord]:
        """Get the complete audit trail for a strategy."""
        return await self.query(strategy_id=strategy_id, limit=limit)

    async def get_errors(self, limit: int = 100) -> list[AuditRecord]:
        """Get error and critical audit records."""
        return await self.query(level=AuditLevel.ERROR, limit=limit) + \
               await self.query(level=AuditLevel.CRITICAL, limit=limit)

    async def count(self) -> int:
        """Get total audit records."""
        return len(self._records)

    async def count_by_category(self) -> dict[str, int]:
        """Get record counts by category."""
        counts: dict[str, int] = {}
        for record in self._records:
            cat = record.category.value if isinstance(record.category, AuditCategory) else str(record.category)
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    async def health_check(self) -> dict[str, Any]:
        """Check audit center health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "total_records": len(self._records),
            "max_records": self._max_records,
            "utilization_pct": (len(self._records) / self._max_records * 100) if self._max_records > 0 else 0,
        }
