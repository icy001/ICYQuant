"""Scheduler Serializer — serializes/deserializes scheduler objects to/from JSON/YAML."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleStatus, ScheduleConfig
from .models.job import JobDefinition, JobState, JobPriority, JobConfig
from .models.execution import ExecutionRecord, ExecutionState, ExecutionResult
from .models.trigger import TriggerDefinition, TriggerType, TriggerState
from .scheduler_snapshot import SchedulerSnapshot

logger = logging.getLogger(__name__)


class SchedulerSerializer:
    """Serializes and deserializes scheduler domain objects.

    Supports JSON and YAML formats for all core scheduler types.
    """

    @staticmethod
    def serialize_schedule(schedule: ScheduleDefinition) -> Dict[str, Any]:
        """Serialize a schedule definition to a dict."""
        return schedule.to_dict()

    @staticmethod
    def deserialize_schedule(data: Dict[str, Any]) -> ScheduleDefinition:
        """Deserialize a schedule definition from a dict."""
        config_dict = data.get("config", {})
        config = ScheduleConfig(
            overlapping_policy=config_dict.get("overlapping_policy", "skip"),
            misfire_policy=config_dict.get("misfire_policy", "ignore"),
            max_concurrent=config_dict.get("max_concurrent", 1),
            timeout_seconds=config_dict.get("timeout_seconds"),
            retry_max=config_dict.get("retry_max", 3),
            retry_delay_seconds=config_dict.get("retry_delay_seconds", 1.0),
            priority=config_dict.get("priority", 100),
            labels=config_dict.get("labels", {}),
            tags=config_dict.get("tags", []),
            metadata=config_dict.get("metadata", {}),
        )
        return ScheduleDefinition(
            schedule_id=data["schedule_id"],
            name=data["name"],
            schedule_type=ScheduleType(data.get("schedule_type", "cron")),
            trigger_expression=data.get("trigger_expression", ""),
            target=data.get("target", ""),
            payload=data.get("payload", {}),
            config=config,
            status=ScheduleStatus(data.get("status", "draft")),
            version=data.get("version", "1.0.0"),
            owner=data.get("owner", ""),
            description=data.get("description", ""),
        )

    @staticmethod
    def serialize_job(job: JobDefinition) -> Dict[str, Any]:
        """Serialize a job definition to a dict."""
        return job.to_dict()

    @staticmethod
    def deserialize_job(data: Dict[str, Any]) -> JobDefinition:
        """Deserialize a job definition from a dict."""
        config_dict = data.get("config", {})
        config = JobConfig(
            timeout_seconds=config_dict.get("timeout_seconds"),
            retry_max=config_dict.get("retry_max", 3),
            retry_delay_seconds=config_dict.get("retry_delay_seconds", 1.0),
            backoff_multiplier=config_dict.get("backoff_multiplier", 2.0),
            resource_requirements=config_dict.get("resource_requirements", {}),
            worker_affinity=config_dict.get("worker_affinity"),
            broadcast=config_dict.get("broadcast", False),
            singleton=config_dict.get("singleton", False),
        )
        return JobDefinition(
            job_id=data["job_id"],
            schedule_id=data["schedule_id"],
            target=data["target"],
            trigger_type=data.get("trigger_type", "unknown"),
            priority=JobPriority(data.get("priority", 50)),
            state=JobState(data.get("state", "created")),
            payload=data.get("payload", {}),
            config=config,
            assigned_worker=data.get("assigned_worker"),
            trace_id=data.get("trace_id"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
            execution_id=data.get("execution_id"),
        )

    @staticmethod
    def serialize_snapshot(snapshot: SchedulerSnapshot) -> Dict[str, Any]:
        """Serialize a scheduler snapshot."""
        return snapshot.to_dict()

    @staticmethod
    def deserialize_snapshot(data: Dict[str, Any]) -> SchedulerSnapshot:
        """Deserialize a scheduler snapshot."""
        return SchedulerSnapshot.from_dict(data)

    @staticmethod
    def to_json(obj: Any) -> str:
        """Convert any serializable object to JSON string."""
        if hasattr(obj, "to_dict"):
            data = obj.to_dict()
        elif isinstance(obj, dict):
            data = obj
        else:
            data = str(obj)
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def from_json(json_str: str, obj_type: str = "schedule") -> Any:
        """Parse a JSON string back into the specified object type."""
        data = json.loads(json_str)
        if obj_type == "schedule":
            return SchedulerSerializer.deserialize_schedule(data)
        elif obj_type == "job":
            return SchedulerSerializer.deserialize_job(data)
        elif obj_type == "snapshot":
            return SchedulerSerializer.deserialize_snapshot(data)
        else:
            raise ValueError(f"Unknown object type: {obj_type}")
