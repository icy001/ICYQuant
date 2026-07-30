"""
MLOps Pipeline Scheduler.

Schedules and manages MLOps pipeline runs:
- Continuous training jobs
- Evaluation jobs
- Drift detection checks
- Champion/challenger evaluations
- Deployment rollouts

Supports CRON-based scheduling, interval-based, and event-driven triggers.
"""

import enum
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ScheduleStatus(str, enum.Enum):
    """Status of a scheduled entry."""
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ScheduleTrigger(str, enum.Enum):
    """What triggers a schedule to run."""
    CRON = "cron"
    INTERVAL = "interval"
    EVENT = "event"
    MANUAL = "manual"
    AT_TIME = "at_time"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SchedulerConfig:
    """Configuration for the MLOps scheduler."""

    # General
    max_concurrent_runs: int = 5
    run_timeout_seconds: float = 7200.0  # 2 hours

    # Default schedules
    default_training_interval_hours: float = 24.0
    default_evaluation_interval_hours: float = 24.0
    default_drift_check_interval_hours: float = 6.0
    default_champion_check_interval_hours: float = 12.0

    # Retry
    max_retries: int = 3
    retry_delay_seconds: float = 300.0

    # Notification
    notify_on_failure: bool = True
    notify_on_success: bool = False


@dataclass
class ScheduleEntry:
    """A single scheduled pipeline run."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    description: str = ""

    # What to run
    pipeline_type: str = ""  # training, evaluation, drift_check, champion_check
    target_model: str = ""
    pipeline_config: Dict[str, Any] = field(default_factory=dict)

    # When to run
    trigger: ScheduleTrigger = ScheduleTrigger.INTERVAL
    cron_expression: str = ""
    interval_seconds: float = 86400.0  # 24 hours default
    at_time: Optional[str] = None  # HH:MM format

    # Status
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    enabled: bool = True

    # Timing
    created_at: float = field(default_factory=time.time)
    last_run_at: Optional[float] = None
    next_run_at: Optional[float] = None
    run_count: int = 0
    failure_count: int = 0

    # Retry
    max_retries: int = 3
    retry_count: int = 0

    # Validity window
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "pipeline_type": self.pipeline_type,
            "target_model": self.target_model,
            "trigger": self.trigger.value,
            "status": self.status.value,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
        }

    def compute_next_run(self) -> Optional[float]:
        """Compute the next run time based on schedule."""
        now = time.time()

        if self.trigger == ScheduleTrigger.INTERVAL:
            base = self.last_run_at or now
            return base + self.interval_seconds

        elif self.trigger == ScheduleTrigger.AT_TIME and self.at_time:
            # Parse HH:MM and set for next occurrence
            try:
                h, m = map(int, self.at_time.split(":"))
                import datetime
                dt = datetime.datetime.fromtimestamp(now)
                target = dt.replace(hour=h, minute=m, second=0, microsecond=0)
                if target.timestamp() <= now:
                    target += datetime.timedelta(days=1)
                return target.timestamp()
            except (ValueError, AttributeError):
                return None

        elif self.trigger == ScheduleTrigger.CRON and self.cron_expression:
            # Simple cron parsing (supports basic patterns)
            return self._parse_cron_next(self.cron_expression, now)

        return None

    @staticmethod
    def _parse_cron_next(cron_expr: str, from_time: float) -> Optional[float]:
        """Parse a simple cron expression to get next run time.

        Supports: "minute hour * * *" or "hour * * *" formats.
        """
        import datetime
        parts = cron_expr.strip().split()
        if len(parts) < 2:
            return None

        try:
            minute = int(parts[0]) if parts[0] != "*" else 0
            hour = int(parts[1]) if parts[1] != "*" else 0
        except ValueError:
            return None

        dt = datetime.datetime.fromtimestamp(from_time)
        target = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target.timestamp() <= from_time:
            target += datetime.timedelta(days=1)

        return target.timestamp()


# ---------------------------------------------------------------------------
# MLOps Scheduler
# ---------------------------------------------------------------------------

class MLOpsScheduler:
    """Schedules and manages MLOps pipeline executions.

    Manages recurring jobs for training, evaluation, drift detection,
    and champion/challenger checks. Supports CRON, interval, and
    event-driven triggers.

    Usage::

        scheduler = MLOpsScheduler(config)
        scheduler.schedule_training("Alpha_v38", interval_hours=24)
        scheduler.schedule_drift_check("Alpha_v38", interval_hours=6)
        scheduler.start()
    """

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self._entries: Dict[str, ScheduleEntry] = {}
        self._running: Dict[str, threading.Thread] = {}
        self._handlers: Dict[str, Callable] = {}
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Schedule Management
    # ------------------------------------------------------------------

    def schedule_training(
        self,
        model_name: str,
        interval_hours: Optional[float] = None,
        cron_expression: Optional[str] = None,
        pipeline_config: Optional[Dict[str, Any]] = None,
    ) -> ScheduleEntry:
        """Schedule continuous training for a model.

        Args:
            model_name: Target model.
            interval_hours: Run every N hours.
            cron_expression: Optional CRON expression.
            pipeline_config: Optional pipeline configuration.

        Returns:
            The created ScheduleEntry.
        """
        trigger = ScheduleTrigger.CRON if cron_expression else ScheduleTrigger.INTERVAL
        interval = (interval_hours or self.config.default_training_interval_hours) * 3600

        entry = ScheduleEntry(
            name=f"Training-{model_name}",
            description=f"Continuous training for {model_name}",
            pipeline_type="training",
            target_model=model_name,
            trigger=trigger,
            cron_expression=cron_expression or "",
            interval_seconds=interval,
            pipeline_config=pipeline_config or {},
        )
        entry.next_run_at = entry.compute_next_run()

        self._entries[entry.entry_id] = entry
        logger.info(f"Scheduled training for {model_name}: every {interval_hours}h")
        return entry

    def schedule_evaluation(
        self,
        model_name: str,
        interval_hours: Optional[float] = None,
    ) -> ScheduleEntry:
        """Schedule continuous evaluation for a model."""
        interval = (interval_hours or self.config.default_evaluation_interval_hours) * 3600

        entry = ScheduleEntry(
            name=f"Evaluation-{model_name}",
            description=f"Continuous evaluation for {model_name}",
            pipeline_type="evaluation",
            target_model=model_name,
            trigger=ScheduleTrigger.INTERVAL,
            interval_seconds=interval,
        )
        entry.next_run_at = entry.compute_next_run()

        self._entries[entry.entry_id] = entry
        logger.info(f"Scheduled evaluation for {model_name}: every {interval_hours}h")
        return entry

    def schedule_drift_check(
        self,
        model_name: str,
        interval_hours: Optional[float] = None,
    ) -> ScheduleEntry:
        """Schedule periodic drift detection."""
        interval = (interval_hours or self.config.default_drift_check_interval_hours) * 3600

        entry = ScheduleEntry(
            name=f"DriftCheck-{model_name}",
            description=f"Drift detection for {model_name}",
            pipeline_type="drift_check",
            target_model=model_name,
            trigger=ScheduleTrigger.INTERVAL,
            interval_seconds=interval,
        )
        entry.next_run_at = entry.compute_next_run()

        self._entries[entry.entry_id] = entry
        logger.info(f"Scheduled drift check for {model_name}: every {interval_hours}h")
        return entry

    def schedule_champion_check(
        self,
        model_name: str,
        interval_hours: Optional[float] = None,
    ) -> ScheduleEntry:
        """Schedule champion/challenger evaluations."""
        interval = (interval_hours or self.config.default_champion_check_interval_hours) * 3600

        entry = ScheduleEntry(
            name=f"ChampionCheck-{model_name}",
            description=f"Champion/challenger evaluation for {model_name}",
            pipeline_type="champion_check",
            target_model=model_name,
            trigger=ScheduleTrigger.INTERVAL,
            interval_seconds=interval,
        )
        entry.next_run_at = entry.compute_next_run()

        self._entries[entry.entry_id] = entry
        logger.info(f"Scheduled champion check for {model_name}: every {interval_hours}h")
        return entry

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler loop in a background thread."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return

        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="mlops-scheduler"
        )
        self._scheduler_thread.start()
        logger.info("MLOps scheduler started")

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
        logger.info("MLOps scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            now = time.time()
            for entry in list(self._entries.values()):
                if not entry.enabled or entry.status == ScheduleStatus.PAUSED:
                    continue
                if entry.next_run_at and now >= entry.next_run_at:
                    self._execute_entry(entry)
            self._stop_event.wait(timeout=1.0)  # Check every second

    def run_now(self, entry_id: str) -> bool:
        """Manually trigger a scheduled entry immediately."""
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        self._execute_entry(entry)
        return True

    def _execute_entry(self, entry: ScheduleEntry) -> None:
        """Execute a scheduled entry."""
        entry.status = ScheduleStatus.RUNNING
        entry.last_run_at = time.time()
        entry.run_count += 1

        logger.info(f"Running scheduled entry: {entry.name} (#{entry.run_count})")

        # Get handler
        handler = self._handlers.get(entry.pipeline_type)
        if handler:
            try:
                result = handler(entry)
                if result:
                    entry.status = ScheduleStatus.COMPLETED
                else:
                    entry.status = ScheduleStatus.FAILED
                    entry.failure_count += 1
            except Exception as e:
                logger.error(f"Schedule entry {entry.name} failed: {e}")
                entry.status = ScheduleStatus.FAILED
                entry.failure_count += 1
        else:
            # No handler, simulate success for testing
            entry.status = ScheduleStatus.COMPLETED

        # Compute next run
        entry.next_run_at = entry.compute_next_run()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def set_handler(self, pipeline_type: str, handler: Callable) -> None:
        """Set the execution handler for a pipeline type.

        Args:
            pipeline_type: Type of pipeline (training, evaluation, etc.).
            handler: Callable that receives ScheduleEntry and returns bool.
        """
        self._handlers[pipeline_type] = handler

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: str) -> Optional[ScheduleEntry]:
        """Get a schedule entry by ID."""
        return self._entries.get(entry_id)

    def list_entries(
        self,
        pipeline_type: Optional[str] = None,
        status: Optional[ScheduleStatus] = None,
    ) -> List[ScheduleEntry]:
        """List schedule entries with filters."""
        entries = list(self._entries.values())
        if pipeline_type:
            entries = [e for e in entries if e.pipeline_type == pipeline_type]
        if status:
            entries = [e for e in entries if e.status == status]
        return entries

    def pause_entry(self, entry_id: str) -> bool:
        """Pause a schedule entry."""
        entry = self._entries.get(entry_id)
        if entry and entry.status == ScheduleStatus.ACTIVE:
            entry.status = ScheduleStatus.PAUSED
            return True
        return False

    def resume_entry(self, entry_id: str) -> bool:
        """Resume a paused schedule entry."""
        entry = self._entries.get(entry_id)
        if entry and entry.status == ScheduleStatus.PAUSED:
            entry.status = ScheduleStatus.ACTIVE
            entry.next_run_at = entry.compute_next_run()
            return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a schedule entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def get_next_runs(self, limit: int = 10) -> List[ScheduleEntry]:
        """Get the next N scheduled runs."""
        active = [
            e for e in self._entries.values()
            if e.enabled and e.status == ScheduleStatus.ACTIVE and e.next_run_at
        ]
        return sorted(active, key=lambda e: e.next_run_at)[:limit]

    def reset(self) -> None:
        """Reset state (for testing)."""
        self.stop()
        self._entries.clear()
        self._running.clear()
        self._handlers.clear()
