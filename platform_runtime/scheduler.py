"""
ICYQuant Platform - Task Scheduler

Manages scheduled tasks: periodic data sync, cleanup, health checks, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import threading

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONCE = "once"


@dataclass
class ScheduledTask:
    name: str
    handler: Callable[[], None]
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    interval_seconds: int = 60
    time_of_day: str = "00:00"
    enabled: bool = True
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def should_run(self, now: Optional[datetime] = None) -> bool:
        if not self.enabled:
            return False
        now = now or datetime.now()
        if self.next_run is None:
            return True
        return now >= self.next_run

    def compute_next_run(self, from_time: Optional[datetime] = None) -> datetime:
        from_time = from_time or datetime.now()
        if self.schedule_type == ScheduleType.INTERVAL:
            return from_time + timedelta(seconds=self.interval_seconds)
        elif self.schedule_type == ScheduleType.DAILY:
            h, m = map(int, self.time_of_day.split(":"))
            next_run = from_time.replace(hour=h, minute=m, second=0)
            if next_run <= from_time:
                next_run += timedelta(days=1)
            return next_run
        return from_time + timedelta(seconds=self.interval_seconds)

    def to_dict(self) -> Dict:
        return {
            "id": self.task_id,
            "name": self.name,
            "scheduleType": self.schedule_type.value,
            "intervalSeconds": self.interval_seconds,
            "enabled": self.enabled,
            "lastRun": self.last_run.isoformat() if self.last_run else None,
            "nextRun": self.next_run.isoformat() if self.next_run else None,
            "runCount": self.run_count,
            "errorCount": self.error_count,
            "lastError": self.last_error,
        }


class TaskScheduler:
    """
    Platform task scheduler.

    Manages scheduled tasks like periodic data sync,
    cleanup routines, and health checks.
    """

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._run_history: List[Dict] = []
        self._max_history = 1000

    def add_task(
        self,
        name: str,
        handler: Callable[[], None],
        schedule_type: ScheduleType = ScheduleType.INTERVAL,
        interval_seconds: int = 60,
        time_of_day: str = "00:00",
        enabled: bool = True,
    ) -> ScheduledTask:
        if name in self._tasks:
            raise ValueError(f"Task '{name}' already exists")

        task = ScheduledTask(
            name=name,
            handler=handler,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            time_of_day=time_of_day,
            enabled=enabled,
        )
        task.next_run = task.compute_next_run()
        self._tasks[task.task_id] = task
        logger.info(f"Scheduled task added: {name}")
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        return True

    def enable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.enabled = True
        task.next_run = task.compute_next_run()
        return True

    def disable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.enabled = False
        return True

    def run_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        try:
            task.handler()
            task.last_run = datetime.now()
            task.run_count += 1
            task.next_run = task.compute_next_run()
            self._run_history.append({
                "task": task.name,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            })
            return True
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            self._run_history.append({
                "task": task.name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            logger.error(f"Task '{task.name}' failed: {e}")
            return False

    def execute_due(self) -> List[str]:
        """Run all tasks that are due."""
        now = datetime.now()
        executed = []
        for task_id, task in list(self._tasks.items()):
            if task.should_run(now):
                self.run_task(task_id)
                executed.append(task.name)
        return executed

    def start(self, interval: float = 1.0):
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._run_loop, args=(interval,), daemon=True
        )
        self._scheduler_thread.start()
        logger.info("Task scheduler started")

    def stop(self):
        """Stop the scheduler background thread."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None
        logger.info("Task scheduler stopped")

    def _run_loop(self, interval: float):
        while self._running:
            try:
                self.execute_due()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            threading.Event().wait(interval)

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks.values())

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._run_history[-limit:]

    def get_status(self) -> Dict:
        tasks = list(self._tasks.values())
        return {
            "totalTasks": len(tasks),
            "enabled": sum(1 for t in tasks if t.enabled),
            "running": self._running,
            "totalRuns": sum(t.run_count for t in tasks),
            "totalErrors": sum(t.error_count for t in tasks),
        }

    def to_dict(self) -> Dict:
        return {
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "status": self.get_status(),
        }
