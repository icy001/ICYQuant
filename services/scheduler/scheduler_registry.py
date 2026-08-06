"""Scheduler Registry — central registry for schedule definitions.

The :class:`SchedulerRegistry` maintains the authoritative catalog of all
registered schedules with support for versioning, dynamic registration,
discovery, and lifecycle management.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleStatus
from .scheduler_validator import validate_schedule

logger = logging.getLogger(__name__)


class SchedulerRegistry:
    """Central registry for all schedule definitions.

    Supports:
    * Cron, Interval, One-shot, Calendar, and Event trigger types
    * Version management and grayscale deployment
    * Dynamic registration and deprecation
    * Discovery and query by type/status

    Usage::

        registry = SchedulerRegistry()
        schedule = registry.register(my_schedule)
        active = registry.list_active()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._schedules: Dict[str, ScheduleDefinition] = {}
        self._by_type: Dict[ScheduleType, List[str]] = {}
        self._by_status: Dict[ScheduleStatus, List[str]] = {}
        self._by_target: Dict[str, List[str]] = {}
        self._version_history: Dict[str, List[ScheduleDefinition]] = {}

        # Metadata
        self._created_at: datetime = datetime.now(timezone.utc)
        self._registration_count: int = 0

    # ── registration ───────────────────────────────────────────────────────

    def register(self, schedule: ScheduleDefinition) -> ScheduleDefinition:
        """Register or update a schedule definition.

        Validates the schedule before registration and updates all
        internal indexes for efficient querying.
        """
        # Validate
        errors = validate_schedule(schedule)
        if errors:
            raise ValueError(f"Schedule validation failed: {errors}")

        with self._lock:
            schedule_id = schedule.schedule_id

            # Track version history
            if schedule_id in self._version_history:
                self._version_history[schedule_id].append(schedule)
            else:
                self._version_history[schedule_id] = [schedule]

            # Mark as registered
            registered = schedule.with_status(ScheduleStatus.REGISTERED)

            # Update main store
            self._schedules[schedule_id] = registered

            # Update type index
            self._by_type.setdefault(registered.schedule_type, []).append(schedule_id)

            # Update status index
            self._by_status.setdefault(registered.status, []).append(schedule_id)

            # Update target index
            self._by_target.setdefault(registered.target, []).append(schedule_id)

            self._registration_count += 1

        logger.info("SchedulerRegistry: registered schedule %s (v%s)", schedule_id, registered.version)
        return registered

    def _update(self, schedule: ScheduleDefinition) -> None:
        """Internal: update a schedule in-place (no validation)."""
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule

    # ── lifecycle ──────────────────────────────────────────────────────────

    def activate(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Activate a registered schedule."""
        return self._transition_status(schedule_id, ScheduleStatus.ACTIVE)

    def pause(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Pause a schedule."""
        return self._transition_status(schedule_id, ScheduleStatus.PAUSED)

    def resume(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Resume a paused schedule."""
        return self._transition_status(schedule_id, ScheduleStatus.ACTIVE)

    def deprecate(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Deprecate a schedule."""
        return self._transition_status(schedule_id, ScheduleStatus.DEPRECATED)

    def archive(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Archive a schedule."""
        return self._transition_status(schedule_id, ScheduleStatus.ARCHIVED)

    def remove(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Remove a schedule entirely from the registry."""
        with self._lock:
            schedule = self._schedules.pop(schedule_id, None)
            if schedule:
                # Clean up indexes
                for idx in [self._by_type, self._by_status, self._by_target]:
                    for key, ids in list(idx.items()):
                        if schedule_id in ids:
                            ids.remove(schedule_id)
                logger.info("SchedulerRegistry: removed schedule %s", schedule_id)
            return schedule

    def _transition_status(
        self, schedule_id: str, target: ScheduleStatus,
    ) -> Optional[ScheduleDefinition]:
        """Transition a schedule to a new status."""
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                return None

            # Remove from old status index
            old_ids = self._by_status.get(schedule.status, [])
            if schedule_id in old_ids:
                old_ids.remove(schedule_id)

            # Transition
            updated = schedule.with_status(target)
            self._schedules[schedule_id] = updated

            # Add to new status index
            self._by_status.setdefault(target, []).append(schedule_id)

            logger.info(
                "SchedulerRegistry: schedule %s %s → %s",
                schedule_id, schedule.status.value, target.value,
            )
            return updated

    # ── query ──────────────────────────────────────────────────────────────

    def get(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Retrieve a schedule by ID."""
        return self._schedules.get(schedule_id)

    def list_all(
        self,
        status: Optional[ScheduleStatus] = None,
        schedule_type: Optional[ScheduleType] = None,
        target: Optional[str] = None,
    ) -> List[ScheduleDefinition]:
        """List schedules with optional filters."""
        with self._lock:
            if status:
                ids = list(self._by_status.get(status, []))
            elif schedule_type:
                ids = list(self._by_type.get(schedule_type, []))
            elif target:
                ids = list(self._by_target.get(target, []))
            else:
                ids = list(self._schedules.keys())

            schedules = [self._schedules[i] for i in ids if i in self._schedules]
            return schedules

    def list_active(self) -> List[ScheduleDefinition]:
        """List all currently active schedules."""
        return self.list_all(status=ScheduleStatus.ACTIVE)

    def list_by_type(self, schedule_type: ScheduleType) -> List[ScheduleDefinition]:
        """List schedules by type."""
        return self.list_all(schedule_type=schedule_type)

    def list_by_target(self, target: str) -> List[ScheduleDefinition]:
        """List schedules targeting a specific workflow/task."""
        return self.list_all(target=target)

    def get_version_history(self, schedule_id: str) -> List[ScheduleDefinition]:
        """Retrieve version history for a schedule."""
        return list(self._version_history.get(schedule_id, []))

    # ── observability ──────────────────────────────────────────────────────

    @property
    def schedule_count(self) -> int:
        return len(self._schedules)

    @property
    def active_count(self) -> int:
        return len(self.list_active())

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report."""
        with self._lock:
            return {
                "total_schedules": len(self._schedules),
                "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
                "by_status": {s.value: len(ids) for s, ids in self._by_status.items()},
                "registration_count": self._registration_count,
                "created_at": self._created_at.isoformat(),
            }
