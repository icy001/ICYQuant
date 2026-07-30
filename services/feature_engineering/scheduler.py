"""Pipeline Scheduler.

Automated scheduling of feature engineering pipelines with
cron-style triggers and dependency management.

Usage::

    from services.feature_engineering import PipelineScheduler, ScheduleConfig

    scheduler = PipelineScheduler()
    scheduler.schedule(
        pipeline_name="alpha_daily",
        trigger="cron:0 3 * * *",
        config=ScheduleConfig(),
    )
    scheduler.start()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.feature_engineering.orchestrator import (
    PipelineOrchestrator,
    RunStatus,
)


class TriggerType(str, Enum):
    """Schedule trigger type."""

    CRON = "cron"          # cron-style expression
    INTERVAL = "interval"  # fixed interval in seconds
    MANUAL = "manual"      # manually triggered
    EVENT = "event"        # event-driven trigger


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled pipeline run.

    Attributes:
        enabled: Whether this schedule is active.
        trigger: Trigger type.
        expression: Trigger expression (cron string or interval seconds).
        timezone: Timezone for cron schedules.
        catch_up: Whether to run missed schedules.
        max_concurrent: Max concurrent runs of this pipeline.
        depends_on: Pipelines that must complete before this one.
        notify_on_complete: Callback on successful completion.
        notify_on_error: Callback on failure.
    """

    enabled: bool = True
    trigger: TriggerType = TriggerType.MANUAL
    expression: str = ""
    timezone: str = "UTC"
    catch_up: bool = False
    max_concurrent: int = 1
    depends_on: List[str] = field(default_factory=list)
    notify_on_complete: Optional[Callable[[str], None]] = None
    notify_on_error: Optional[Callable[[str, str], None]] = None


@dataclass
class ScheduleEntry:
    """A single schedule entry in the scheduler.

    Attributes:
        pipeline_name: Name of the pipeline to run.
        config: Schedule configuration.
        last_run: Timestamp of last execution.
        next_run: Timestamp of next scheduled execution.
        run_count: Total number of executions.
        last_status: Status of last execution.
    """

    pipeline_name: str
    config: ScheduleConfig = field(default_factory=ScheduleConfig)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    last_status: Optional[RunStatus] = None

    def __repr__(self) -> str:
        return (
            f"ScheduleEntry(pipeline={self.pipeline_name}, "
            f"trigger={self.config.trigger.value}, "
            f"runs={self.run_count})"
        )


class PipelineScheduler:
    """Automated scheduler for feature engineering pipelines.

    Supports cron-style and interval-based scheduling, dependency
    management between pipelines, and concurrent execution control.

    Example::

        scheduler = PipelineScheduler(orchestrator=orch)
        scheduler.schedule("alpha_daily", trigger="cron:0 3 * * *")
        scheduler.schedule("factor_hourly", trigger="interval:3600")
        scheduler.start()

        # ... pipelines run automatically ...

        scheduler.stop()
    """

    def __init__(self, orchestrator: Optional[PipelineOrchestrator] = None) -> None:
        self._orchestrator = orchestrator or PipelineOrchestrator()
        self._schedules: Dict[str, ScheduleEntry] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

    # ---- Schedule management ----

    def schedule(
        self,
        pipeline_name: str,
        config: Optional[ScheduleConfig] = None,
        trigger: Optional[str] = None,
    ) -> ScheduleEntry:
        """Add or update a schedule for a pipeline.

        Args:
            pipeline_name: Name of the registered pipeline.
            config: Schedule configuration.
            trigger: Shorthand trigger string (e.g. "cron:0 3 * * *" or "interval:3600").

        Returns:
            The created/updated ScheduleEntry.
        """
        config = config or ScheduleConfig()

        if trigger:
            config = self._parse_trigger(trigger, config)

        entry = ScheduleEntry(
            pipeline_name=pipeline_name,
            config=config,
        )
        entry.next_run = self._compute_next_run(config)

        with self._lock:
            self._schedules[pipeline_name] = entry

        return entry

    def unschedule(self, pipeline_name: str) -> bool:
        """Remove a schedule. Returns True if it existed."""
        with self._lock:
            if pipeline_name in self._schedules:
                del self._schedules[pipeline_name]
                return True
        return False

    def get_schedule(self, pipeline_name: str) -> Optional[ScheduleEntry]:
        """Get schedule entry for a pipeline."""
        return self._schedules.get(pipeline_name)

    def list_schedules(self) -> List[ScheduleEntry]:
        """List all active schedules."""
        return list(self._schedules.values())

    # ---- Lifecycle ----

    def start(self) -> None:
        """Start the scheduler loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        self._shutdown_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- Manual trigger ----

    def trigger(self, pipeline_name: str, raw_data: Dict[str, List[float]]) -> bool:
        """Manually trigger a pipeline run.

        Args:
            pipeline_name: Pipeline to run.
            raw_data: Input data.

        Returns:
            True if triggered successfully.
        """
        entry = self._schedules.get(pipeline_name)
        if entry is None:
            return False

        try:
            self._orchestrator.run(pipeline_name, raw_data)
            with self._lock:
                entry.last_run = time.time()
                entry.run_count += 1
            return True
        except Exception:
            return False

    def trigger_all(self, raw_data: Dict[str, List[float]]) -> Dict[str, bool]:
        """Manually trigger all scheduled pipelines."""
        results: Dict[str, bool] = {}
        for name in list(self._schedules.keys()):
            results[name] = self.trigger(name, raw_data)
        return results

    # ---- Internal scheduler loop ----

    def _scheduler_loop(self) -> None:
        """Main scheduler loop running in background thread."""
        while self._running and not self._shutdown_event.is_set():
            now = time.time()

            with self._lock:
                for entry in list(self._schedules.values()):
                    if not entry.config.enabled:
                        continue
                    if entry.next_run and now >= entry.next_run:
                        self._execute_scheduled(entry)

            # Sleep for a short interval before checking again
            self._shutdown_event.wait(timeout=1.0)

    def _execute_scheduled(self, entry: ScheduleEntry) -> None:
        """Execute a scheduled pipeline run."""
        pipeline_name = entry.pipeline_name

        # Check dependencies
        if not self._dependencies_satisfied(entry):
            entry.next_run = self._compute_next_run(entry.config, after=time.time())
            return

        try:
            # Execute via orchestrator
            self._orchestrator.run(pipeline_name, {})
            entry.last_status = RunStatus.SUCCESS
            if entry.config.notify_on_complete:
                entry.config.notify_on_complete(pipeline_name)
        except Exception as e:
            entry.last_status = RunStatus.FAILED
            if entry.config.notify_on_error:
                entry.config.notify_on_error(pipeline_name, str(e))

        entry.last_run = time.time()
        entry.run_count += 1
        entry.next_run = self._compute_next_run(entry.config, after=time.time())

    def _dependencies_satisfied(self, entry: ScheduleEntry) -> bool:
        """Check if all dependency pipelines have completed."""
        for dep in entry.config.depends_on:
            dep_entry = self._schedules.get(dep)
            if dep_entry is None:
                continue
            if dep_entry.last_status == RunStatus.FAILED:
                return False
            if dep_entry.last_status is None:
                return False  # hasn't run yet
        return True

    # ---- Trigger parsing ----

    def _parse_trigger(self, trigger: str, config: ScheduleConfig) -> ScheduleConfig:
        """Parse a trigger string into ScheduleConfig fields.

        Formats:
            - "cron:0 3 * * *"
            - "interval:3600"
            - "manual"
            - "event:market_close"
        """
        if trigger.startswith("cron:"):
            config.trigger = TriggerType.CRON
            config.expression = trigger[5:]
        elif trigger.startswith("interval:"):
            config.trigger = TriggerType.INTERVAL
            config.expression = trigger[9:]
        elif trigger.startswith("event:"):
            config.trigger = TriggerType.EVENT
            config.expression = trigger[6:]
        else:
            config.trigger = TriggerType.MANUAL
            config.expression = ""
        return config

    # ---- Next run computation ----

    def _compute_next_run(
        self,
        config: ScheduleConfig,
        after: Optional[float] = None,
    ) -> Optional[float]:
        """Compute the next run timestamp.

        Args:
            config: Schedule configuration.
            after: Base time to compute from (default: now).

        Returns:
            Next run timestamp or None for manual triggers.
        """
        now = after or time.time()

        if config.trigger == TriggerType.MANUAL:
            return None
        elif config.trigger == TriggerType.INTERVAL:
            try:
                interval = float(config.expression)
                return now + interval
            except (ValueError, TypeError):
                return None
        elif config.trigger == TriggerType.CRON:
            return self._cron_next(config.expression, now)
        elif config.trigger == TriggerType.EVENT:
            return None  # event-driven, no fixed next run
        return None

    def _cron_next(self, expression: str, from_time: float) -> Optional[float]:
        """Compute next cron trigger time.

        Supports simplified 5-field cron: minute hour day month weekday.

        Args:
            expression: Cron expression.
            from_time: Reference timestamp.

        Returns:
            Next trigger timestamp.
        """
        try:
            parts = expression.strip().split()
            if len(parts) != 5:
                # Fallback: return 1 hour from now
                return from_time + 3600

            minute, hour, day, month, weekday = parts

            from_struct = time.localtime(from_time)

            # Simple implementation: if hour matches and minute hasn't passed
            target_hour = self._cron_field(hour, 0, 23)
            target_minute = self._cron_field(minute, 0, 59)

            if target_hour is None or target_minute is None:
                return from_time + 3600  # fallback

            # Build next time
            next_struct = list(from_struct)
            next_struct[3] = target_hour  # tm_hour
            next_struct[4] = target_minute  # tm_min
            next_struct[5] = 0  # tm_sec

            candidate = time.mktime(tuple(next_struct))
            if candidate <= from_time:
                candidate += 86400  # next day

            return candidate
        except Exception:
            return None

    @staticmethod
    def _cron_field(field: str, lo: int, hi: int) -> Optional[int]:
        """Parse a single cron field. Returns an integer or None for '*'.

        Supports: '*', single integer, comma-separated list.
        """
        field = field.strip()
        if field == "*":
            return None  # wildcard
        try:
            return int(field)
        except ValueError:
            pass
        # Comma-separated: take the first
        parts = field.split(",")
        try:
            return int(parts[0].strip())
        except (ValueError, IndexError):
            return None

    # ---- Summary ----

    def summary(self) -> Dict[str, Any]:
        """Return scheduler summary."""
        entries = self._schedules
        return {
            "running": self._running,
            "total_schedules": len(entries),
            "active": sum(1 for e in entries.values() if e.config.enabled),
            "paused": sum(1 for e in entries.values() if not e.config.enabled),
            "schedules": {
                name: {
                    "trigger": e.config.trigger.value,
                    "last_run": e.last_run,
                    "next_run": e.next_run,
                    "run_count": e.run_count,
                }
                for name, e in entries.items()
            },
        }

    def __repr__(self) -> str:
        return f"PipelineScheduler(running={self._running}, schedules={len(self._schedules)})"
