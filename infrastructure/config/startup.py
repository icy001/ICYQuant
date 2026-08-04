"""
Configuration startup process.

Manages the detailed startup sequence for the
configuration platform, ensuring correct
initialization order and dependency resolution.

Startup Flow:
    1. Validate prerequisites
    2. Initialize components
    3. Load configuration sources
    4. Resolve environment
    5. Build initial snapshot
    6. Start watchers
    7. Mark as ready
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StartupPhase(str, Enum):
    """Startup phases."""

    VALIDATION = "validation"
    INITIALIZATION = "initialization"
    LOADING = "loading"
    ENVIRONMENT = "environment"
    SNAPSHOT = "snapshot"
    WATCHER = "watcher"
    READY = "ready"


class StartupResult:
    """
    Result of the startup process.

    Attributes:
        success: Whether startup succeeded.
        phase: Last completed phase.
        duration: Startup duration.
        errors: List of errors.
        components: Initialized components.
    """

    def __init__(
        self,
        success: bool,
        phase: str = "",
        duration: float = 0.0,
        errors: Optional[List[str]] = None,
        components: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.success = success
        self.phase = phase
        self.duration = duration
        self.errors = errors or []
        self.components = components or {}

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "success": self.success,
            "phase": self.phase,
            "duration": self.duration,
            "errors": self.errors,
            "components": list(self.components.keys()),
        }


class ConfigurationStartup:
    """
    Configuration platform startup manager.

    Executes the detailed startup sequence with
    proper ordering and error handling.

    Usage:
        startup = ConfigurationStartup()
        result = await startup.execute()
    """

    def __init__(
        self,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize startup manager.

        Args:
            steps: Custom startup steps.
        """
        self._steps: List[Dict[str, Any]] = steps or self._default_steps()
        self._results: List[Dict[str, Any]] = []
        self._completed = False

    @property
    def results(
        self,
    ) -> List[Dict[str, Any]]:
        """Get step results."""
        return list(self._results)

    def add_step(
        self,
        name: str,
        func: Callable,
        required: bool = True,
    ) -> None:
        """
        Add a startup step.

        Args:
            name: Step name.
            func: Step function.
            required: If True, failure stops startup.
        """
        self._steps.append({
            "name": name,
            "func": func,
            "required": required,
        })

    async def execute(
        self,
    ) -> StartupResult:
        """
        Execute the startup sequence.

        Returns:
            StartupResult.
        """
        start = datetime.utcnow()
        self._results.clear()
        components: Dict[str, Any] = {}
        errors: List[str] = []
        last_phase = ""

        for step in self._steps:
            step_name = step["name"]
            step_func = step["func"]
            required = step.get("required", True)

            step_start = datetime.utcnow()
            try:
                result = step_func()
                if asyncio.iscoroutine(result):
                    result = await result

                if result is not None:
                    components[step_name] = result

                elapsed = (datetime.utcnow() - step_start).total_seconds()
                self._results.append({
                    "step": step_name,
                    "status": "ok",
                    "elapsed": elapsed,
                })
                last_phase = step_name

            except Exception as e:
                elapsed = (datetime.utcnow() - step_start).total_seconds()
                self._results.append({
                    "step": step_name,
                    "status": "error",
                    "error": str(e),
                    "elapsed": elapsed,
                })
                errors.append(f"{step_name}: {e}")

                if required:
                    duration = (datetime.utcnow() - start).total_seconds()
                    return StartupResult(
                        success=False,
                        phase=last_phase,
                        duration=duration,
                        errors=errors,
                        components=components,
                    )

        duration = (datetime.utcnow() - start).total_seconds()
        self._completed = True

        return StartupResult(
            success=True,
            phase=last_phase,
            duration=duration,
            errors=errors,
            components=components,
        )

    def _default_steps(
        self,
    ) -> List[Dict[str, Any]]:
        """Get default startup steps."""
        return [
            {"name": "validate", "func": self._validate_prerequisites, "required": True},
            {"name": "init_config", "func": self._init_config, "required": True},
            {"name": "init_environment", "func": self._init_environment, "required": True},
            {"name": "init_registry", "func": self._init_registry, "required": True},
            {"name": "init_dynamic", "func": self._init_dynamic, "required": False},
            {"name": "init_watcher", "func": self._init_watcher, "required": False},
            {"name": "mark_ready", "func": self._mark_ready, "required": True},
        ]

    def _validate_prerequisites(
        self,
    ) -> bool:
        """Validate startup prerequisites."""
        import sys
        if sys.version_info < (3, 9):
            raise RuntimeError("Python 3.9+ required")
        return True

    def _init_config(
        self,
    ) -> Any:
        """Initialize configuration manager."""
        from .manager import ConfigurationManager
        return ConfigurationManager()

    def _init_environment(
        self,
    ) -> Any:
        """Initialize environment manager."""
        from .environment.manager import EnvironmentManager
        mgr = EnvironmentManager()
        mgr.init_standard_profiles()
        mgr.auto_detect()
        return mgr

    def _init_registry(
        self,
    ) -> Any:
        """Initialize registry."""
        from .registry import ConfigurationRegistry
        return ConfigurationRegistry()

    def _init_dynamic(
        self,
    ) -> Any:
        """Initialize dynamic configuration manager."""
        from .dynamic.manager import DynamicConfigurationManager
        return DynamicConfigurationManager()

    def _init_watcher(
        self,
    ) -> Any:
        """Initialize watcher."""
        from .dynamic.watcher import ConfigurationWatcher
        return ConfigurationWatcher()

    def _mark_ready(
        self,
    ) -> bool:
        """Mark platform as ready."""
        return True
