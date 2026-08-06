"""Scheduler Loader — loads schedule definitions from YAML/JSON/dict sources.

The :class:`SchedulerLoader` deserializes schedule definitions from
configuration files and registers them into the scheduler registry.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleConfig
from .scheduler_registry import SchedulerRegistry

logger = logging.getLogger(__name__)


class SchedulerLoader:
    """Load schedule definitions from configuration sources.

    Supports loading from YAML files, JSON files, and Python dictionaries.
    Integrates with the registry for bulk registration.

    Usage::

        loader = SchedulerLoader(registry)
        loader.load_from_file("configs/schedules/production.yaml")
    """

    def __init__(self, registry: Optional[SchedulerRegistry] = None) -> None:
        self._registry = registry or SchedulerRegistry()
        self._loaded_schedules: List[ScheduleDefinition] = []

    def load_from_file(self, filepath: str) -> List[ScheduleDefinition]:
        """Load schedules from a YAML or JSON configuration file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Schedule config not found: {filepath}")

        if path.suffix in (".yaml", ".yml"):
            return self._load_yaml_file(path)
        elif path.suffix == ".json":
            return self._load_json_file(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def load_from_dict(self, data: Dict[str, Any]) -> List[ScheduleDefinition]:
        """Load schedules from a dictionary."""
        schedules: List[ScheduleDefinition] = []

        # Support both {schedules: [...]} and direct schedule dict
        schedule_list = data.get("schedules", [data] if "schedule_id" in data or "name" in data else [])
        if not isinstance(schedule_list, list):
            schedule_list = [schedule_list]

        for item in schedule_list:
            try:
                schedule = self._parse_schedule(item)
                if schedule:
                    schedules.append(schedule)
            except Exception:
                logger.exception("SchedulerLoader: failed to parse schedule")

        self._loaded_schedules.extend(schedules)
        return schedules

    def load_from_json_string(self, json_str: str) -> List[ScheduleDefinition]:
        """Load schedules from a JSON string."""
        data = json.loads(json_str)
        return self.load_from_dict(data)

    def register_all(self) -> List[ScheduleDefinition]:
        """Register all loaded schedules into the registry."""
        registered: List[ScheduleDefinition] = []
        for schedule in self._loaded_schedules:
            try:
                reg = self._registry.register(schedule)
                registered.append(reg)
            except ValueError as exc:
                logger.warning(
                    "SchedulerLoader: failed to register schedule %s: %s",
                    schedule.schedule_id, exc,
                )
        logger.info("SchedulerLoader: registered %d/%d schedules", len(registered), len(self._loaded_schedules))
        return registered

    def activate_all(self) -> List[ScheduleDefinition]:
        """Activate all registered schedules."""
        activated: List[ScheduleDefinition] = []
        for schedule in self._loaded_schedules:
            result = self._registry.activate(schedule.schedule_id)
            if result:
                activated.append(result)
        return activated

    # ── internal ───────────────────────────────────────────────────────────

    def _parse_schedule(self, data: Dict[str, Any]) -> Optional[ScheduleDefinition]:
        """Parse a single schedule from dict."""
        schedule_id = data.get("schedule_id", "")
        if not schedule_id:
            return None

        schedule_type = ScheduleType(data.get("schedule_type", "cron"))

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
            schedule_id=schedule_id,
            name=data.get("name", schedule_id),
            schedule_type=schedule_type,
            trigger_expression=data.get("trigger_expression", ""),
            target=data.get("target", ""),
            payload=data.get("payload", {}),
            config=config,
            version=data.get("version", "1.0.0"),
            owner=data.get("owner", ""),
            description=data.get("description", ""),
        )

    def _load_yaml_file(self, path: Path) -> List[ScheduleDefinition]:
        """Load schedules from a YAML file."""
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("PyYAML is required for YAML schedule loading. Install with: pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self.load_from_dict(data or {})

    def _load_json_file(self, path: Path) -> List[ScheduleDefinition]:
        """Load schedules from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.load_from_dict(data)

    @property
    def loaded_count(self) -> int:
        return len(self._loaded_schedules)
