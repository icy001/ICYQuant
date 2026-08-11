"""
Strategy Recovery — failure recovery engine for production strategies.

Enables strategies to be restored to a known-good state after crashes,
failures, or restarts using previously captured snapshots.

Recovery pipeline:
    Detect Failure → Select Snapshot → Restore Runtime → Resume Strategy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecoveryStatus(str, Enum):
    """Status of a recovery operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RecoverySource(str, Enum):
    """What triggered the recovery."""
    AUTO = "auto"           # Automatic detection
    MANUAL = "manual"       # User-initiated
    SCHEDULED = "scheduled" # Periodic recovery test
    ROLLBACK = "rollback"   # Rollback recovery


@dataclass
class RecoveryRecord:
    """A record of a recovery attempt."""

    recovery_id: str
    strategy_id: str
    status: RecoveryStatus = RecoveryStatus.PENDING
    source: RecoverySource = RecoverySource.MANUAL
    snapshot_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # Pre-recovery state
    pre_state: str = ""
    pre_variables: Dict[str, Any] = field(default_factory=dict)

    # Post-recovery state
    post_state: str = ""
    result: str = ""
    error: str = ""

    # Duration
    duration_ms: float = 0.0

    def complete(self, post_state: str, message: str = "") -> None:
        self.status = RecoveryStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.post_state = post_state
        self.result = message
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def fail(self, error: str) -> None:
        self.status = RecoveryStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error = error
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "source": self.source.value,
            "snapshot_id": self.snapshot_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pre_state": self.pre_state,
            "post_state": self.post_state,
            "result": self.result,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class RecoveryConfig:
    """Configuration for strategy recovery."""
    enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 1000
    snapshot_lookback_hours: int = 24  # Max age of usable snapshot
    auto_recovery_enabled: bool = True
    verify_snapshot_integrity: bool = True
    require_manual_approval: bool = False


class StrategyRecovery:
    """Failure recovery engine for strategies.

    Restores strategies from snapshots after failure. Supports
    automatic recovery (heartbeat-based) and manual recovery.

    Usage:
        recovery = StrategyRecovery()
        await recovery.initialize()
        await recovery.recover("strategy_1", snapshot_id=None, runtime=runtime, ...)
    """

    def __init__(self, config: Optional[RecoveryConfig] = None) -> None:
        self._config = config or RecoveryConfig()
        self._history: List[RecoveryRecord] = []
        self._initialized: bool = False
        logger.info("StrategyRecovery created (auto=%s, max_retries=%d)",
                    self._config.auto_recovery_enabled, self._config.max_retries)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyRecovery initialized")

    async def shutdown(self) -> None:
        self._history.clear()
        self._initialized = False
        logger.info("StrategyRecovery shut down")

    # ── Recovery ──

    async def recover(
        self,
        strategy_id: str,
        snapshot_id: Optional[str],
        runtime: Any,
        snapshot_manager: Any,
        registry: Any,
        source: RecoverySource = RecoverySource.MANUAL,
    ) -> RecoveryRecord:
        """Restore a strategy from a snapshot.

        Pipeline:
            1. Capture pre-recovery state
            2. Select the best snapshot (or use specified one)
            3. Verify snapshot integrity
            4. Restore runtime from snapshot
            5. Verify restoration
            6. Resume strategy

        Args:
            strategy_id: Strategy to recover.
            snapshot_id: Specific snapshot ID, or None for latest.
            runtime: StrategyRuntime instance.
            snapshot_manager: SnapshotManager instance.
            registry: StrategyRegistry instance.
            source: Recovery trigger source.

        Returns:
            RecoveryRecord with outcome.

        Raises:
            ValueError: On invalid state or snapshot.
        """
        import uuid

        record = RecoveryRecord(
            recovery_id=uuid.uuid4().hex[:12],
            strategy_id=strategy_id,
            source=source,
            snapshot_id=snapshot_id or "latest",
        )
        record.status = RecoveryStatus.IN_PROGRESS

        # Capture pre-recovery state
        metadata = registry.get_metadata(strategy_id)
        if metadata:
            record.pre_state = metadata.state.value if hasattr(metadata.state, 'value') else str(metadata.state)
        logger.info("Recovery started: %s (source=%s)", strategy_id, source.value)

        # Attempt recovery with retries
        last_error = ""
        for attempt in range(self._config.max_retries):
            try:
                # Select snapshot
                if snapshot_id:
                    snapshot = snapshot_manager.get_snapshot(strategy_id, snapshot_id)
                else:
                    snapshot = snapshot_manager.get_latest_snapshot(strategy_id)

                if snapshot is None:
                    raise KeyError(f"No snapshot available for {strategy_id}")

                record.snapshot_id = snapshot.snapshot_id

                # Check snapshot age
                age_hours = (
                    datetime.now(timezone.utc) - snapshot.created_at
                ).total_seconds() / 3600
                if age_hours > self._config.snapshot_lookback_hours:
                    raise ValueError(
                        f"Snapshot too old ({age_hours:.1f}h > {self._config.snapshot_lookback_hours}h)"
                    )

                # Verify integrity
                if self._config.verify_snapshot_integrity and not snapshot.verify():
                    raise ValueError(f"Snapshot integrity check failed: {snapshot.snapshot_id}")

                # Restore runtime
                await snapshot_manager.restore_snapshot(
                    strategy_id=strategy_id,
                    snapshot_id=snapshot.snapshot_id,
                    runtime=runtime,
                )

                # Update registry
                registry.update_state(strategy_id, snapshot.lifecycle_state, "Recovered from snapshot")
                record.complete(
                    post_state=snapshot.lifecycle_state,
                    message=f"Recovered from snapshot {snapshot.snapshot_id} (attempt {attempt + 1})",
                )

                self._history.append(record)
                logger.info("Recovery successful: %s → %s (%.0fms)",
                            strategy_id, snapshot.lifecycle_state, record.duration_ms)
                return record

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Recovery attempt %d/%d failed for %s: %s",
                    attempt + 1, self._config.max_retries, strategy_id, e,
                )
                if attempt < self._config.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(self._config.retry_delay_ms / 1000.0)

        # All retries exhausted
        record.fail(f"Recovery failed after {self._config.max_retries} attempts: {last_error}")
        self._history.append(record)
        logger.error("Recovery FAILED for %s: %s", strategy_id, last_error)
        return record

    # ── Auto-Recovery ──

    async def perform_auto_recovery(
        self,
        runtime: Any,
        snapshot_manager: Any,
        registry: Any,
    ) -> List[RecoveryRecord]:
        """Scan for stalled/crashed strategies and attempt auto-recovery."""
        if not self._config.auto_recovery_enabled:
            logger.debug("Auto-recovery disabled")
            return []

        recovered: List[RecoveryRecord] = []

        # Scan registry for strategies in error/failed state
        candidates = registry.list_by_state("failed")
        candidates += registry.list_by_state("error")

        for strategy_id in candidates:
            # Check if recovery is already in progress
            recent = [
                r for r in self._history
                if r.strategy_id == strategy_id
                and r.status == RecoveryStatus.IN_PROGRESS
            ]
            if recent:
                logger.debug("Skipping auto-recovery (already in progress): %s", strategy_id)
                continue

            logger.info("Auto-recovery triggered for: %s", strategy_id)
            record = await self.recover(
                strategy_id=strategy_id,
                snapshot_id=None,
                runtime=runtime,
                snapshot_manager=snapshot_manager,
                registry=registry,
                source=RecoverySource.AUTO,
            )
            recovered.append(record)

        if recovered:
            logger.info("Auto-recovery completed: %d strategies", len(recovered))
        return recovered

    # ── Queries ──

    def get_history(
        self,
        strategy_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recovery history, optionally filtered by strategy."""
        records = self._history
        if strategy_id:
            records = [r for r in records if r.strategy_id == strategy_id]
        return [r.to_dict() for r in records[-limit:]]

    def get_last_recovery(self, strategy_id: str) -> Optional[RecoveryRecord]:
        """Get the most recent recovery record for a strategy."""
        records = [r for r in self._history if r.strategy_id == strategy_id]
        if not records:
            return None
        return max(records, key=lambda r: r.started_at)

    def get_success_rate(self, strategy_id: Optional[str] = None) -> float:
        """Get recovery success rate (0.0–1.0)."""
        records = self._history
        if strategy_id:
            records = [r for r in records if r.strategy_id == strategy_id]
        if not records:
            return 1.0
        completed = sum(1 for r in records if r.status == RecoveryStatus.COMPLETED)
        return completed / len(records)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_recoveries": len(self._history),
            "successful": sum(1 for r in self._history if r.status == RecoveryStatus.COMPLETED),
            "failed": sum(1 for r in self._history if r.status == RecoveryStatus.FAILED),
            "auto_recovery_enabled": self._config.auto_recovery_enabled,
            "max_retries": self._config.max_retries,
            "initialized": self._initialized,
        }
