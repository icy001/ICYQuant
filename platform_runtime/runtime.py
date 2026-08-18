"""
ICYQuant Platform - Runtime Manager

Unified runtime for managing module startup, shutdown, restart, and hot reload.
Provides runtime state tracking and module lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class RuntimeState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    STOPPING = "stopping"
    ERROR = "error"
    DEGRADED = "degraded"
    HOT_RELOADING = "hot_reloading"


@dataclass
class ModuleRuntime:
    module_name: str
    state: RuntimeState = RuntimeState.STOPPED
    instance: Optional[Any] = None
    start_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_status: bool = False
    restarts: int = 0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    handlers: Dict[str, Callable] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "moduleName": self.module_name,
            "state": self.state.value,
            "healthStatus": self.health_status,
            "startTime": self.start_time.isoformat() if self.start_time else None,
            "lastHealthCheck": self.last_health_check.isoformat() if self.last_health_check else None,
            "restarts": self.restarts,
            "error": self.error_message,
        }


class RuntimeManager:
    """
    Unified runtime for platform modules.

    Manages startup sequences, shutdown, restart, hot reload,
    and real-time module state tracking.
    """

    def __init__(self):
        self._runtimes: Dict[str, ModuleRuntime] = {}
        self._startup_order: List[str] = []
        self._state_history: List[Dict] = []
        self._max_history = 500
        self._global_state: RuntimeState = RuntimeState.STOPPED
        self._event_callbacks: Dict[str, List[Callable]] = {}

    def register_module(
        self,
        name: str,
        instance: Optional[Any] = None,
        handlers: Optional[Dict[str, Callable]] = None,
    ) -> ModuleRuntime:
        runtime = ModuleRuntime(
            module_name=name,
            instance=instance,
            handlers=handlers or {},
        )
        self._runtimes[name] = runtime
        self._log_state_change(name, None, runtime.state)
        logger.info(f"Module registered in runtime: {name}")
        return runtime

    def unregister_module(self, name: str) -> bool:
        if name not in self._runtimes:
            return False
        self.shutdown_module(name)
        del self._runtimes[name]
        logger.info(f"Module unregistered from runtime: {name}")
        return True

    def startup_module(self, name: str) -> bool:
        rt = self._runtimes.get(name)
        if not rt:
            return False

        old_state = rt.state
        rt.state = RuntimeState.STARTING
        self._log_state_change(name, old_state, rt.state)

        start_fn = rt.handlers.get("start")
        if start_fn:
            try:
                start_fn(rt.instance)
            except Exception as e:
                rt.state = RuntimeState.ERROR
                rt.error_message = str(e)
                self._log_state_change(name, old_state, rt.state)
                logger.error(f"Failed to start module '{name}': {e}")
                return False

        rt.state = RuntimeState.RUNNING
        rt.start_time = datetime.now()
        rt.health_status = True
        self._log_state_change(name, old_state, rt.state)
        logger.info(f"Module started: {name}")
        return True

    def shutdown_module(self, name: str) -> bool:
        rt = self._runtimes.get(name)
        if not rt:
            return False

        old_state = rt.state
        rt.state = RuntimeState.STOPPING
        self._log_state_change(name, old_state, rt.state)

        stop_fn = rt.handlers.get("stop")
        if stop_fn:
            try:
                stop_fn(rt.instance)
            except Exception as e:
                logger.warning(f"Error stopping module '{name}': {e}")

        rt.state = RuntimeState.STOPPED
        rt.health_status = False
        rt.instance = None
        self._log_state_change(name, old_state, rt.state)
        logger.info(f"Module stopped: {name}")
        return True

    def restart_module(self, name: str) -> bool:
        rt = self._runtimes.get(name)
        if not rt:
            return False

        old_state = rt.state
        rt.state = RuntimeState.RESTARTING
        rt.restarts += 1
        self._log_state_change(name, old_state, rt.state)

        self.shutdown_module(name)
        self.startup_module(name)
        return rt.state == RuntimeState.RUNNING

    def hot_reload_module(self, name: str, new_instance: Optional[Any] = None) -> bool:
        rt = self._runtimes.get(name)
        if not rt:
            return False

        old_state = rt.state
        rt.state = RuntimeState.HOT_RELOADING
        self._log_state_change(name, old_state, rt.state)

        reload_fn = rt.handlers.get("reload")
        if reload_fn:
            try:
                reload_fn(rt.instance, new_instance)
            except Exception as e:
                rt.state = RuntimeState.ERROR
                rt.error_message = str(e)
                self._log_state_change(name, old_state, rt.state)
                return False
        elif new_instance:
            rt.instance = new_instance

        rt.state = RuntimeState.RUNNING
        self._log_state_change(name, old_state, rt.state)
        logger.info(f"Module hot-reloaded: {name}")
        return True

    def pause_module(self, name: str) -> bool:
        rt = self._runtimes.get(name)
        if not rt or rt.state != RuntimeState.RUNNING:
            return False

        old_state = rt.state
        rt.state = RuntimeState.PAUSED
        self._log_state_change(name, old_state, rt.state)
        return True

    def resume_module(self, name: str) -> bool:
        rt = self._runtimes.get(name)
        if not rt or rt.state != RuntimeState.PAUSED:
            return False

        old_state = rt.state
        rt.state = RuntimeState.RUNNING
        self._log_state_change(name, old_state, rt.state)
        return True

    def get_runtime(self, name: str) -> Optional[ModuleRuntime]:
        return self._runtimes.get(name)

    def get_module_state(self, name: str) -> RuntimeState:
        rt = self._runtimes.get(name)
        return rt.state if rt else RuntimeState.STOPPED

    def get_all_runtimes(self) -> List[ModuleRuntime]:
        return list(self._runtimes.values())

    def get_running(self) -> List[ModuleRuntime]:
        return [rt for rt in self._runtimes.values() if rt.state == RuntimeState.RUNNING]

    def get_failed(self) -> List[ModuleRuntime]:
        return [rt for rt in self._runtimes.values() if rt.state == RuntimeState.ERROR]

    def run_startup_sequence(self, startup_order: List[str]) -> Dict[str, bool]:
        self._startup_order = startup_order
        results = {}
        self._global_state = RuntimeState.STARTING

        for name in startup_order:
            success = self.startup_module(name)
            results[name] = success
            if not success:
                logger.error(f"Startup sequence failed at: {name}")
                self._global_state = RuntimeState.ERROR
                break

        if all(results.values()):
            self._global_state = RuntimeState.RUNNING
        elif any(results.values()):
            self._global_state = RuntimeState.DEGRADED

        return results

    def run_shutdown_sequence(self, shutdown_order: Optional[List[str]] = None) -> Dict[str, bool]:
        if shutdown_order is None:
            shutdown_order = list(reversed(self._startup_order))

        results = {}
        self._global_state = RuntimeState.STOPPING

        for name in shutdown_order:
            if name in self._runtimes:
                results[name] = self.shutdown_module(name)

        self._global_state = RuntimeState.STOPPED
        return results

    def get_global_state(self) -> RuntimeState:
        return self._global_state

    def run_health_checks(self) -> Dict[str, bool]:
        results = {}
        now = datetime.now()
        for name, rt in self._runtimes.items():
            health_fn = rt.handlers.get("health_check")
            if health_fn:
                try:
                    rt.health_status = health_fn(rt.instance)
                except Exception:
                    rt.health_status = False
            else:
                rt.health_status = rt.state == RuntimeState.RUNNING
            rt.last_health_check = now
            results[name] = rt.health_status
        return results

    def _log_state_change(self, name: str, old_state: Optional[RuntimeState], new_state: RuntimeState):
        entry = {
            "module": name,
            "from": old_state.value if old_state else None,
            "to": new_state.value,
            "timestamp": datetime.now().isoformat(),
        }
        self._state_history.append(entry)
        if len(self._state_history) > self._max_history:
            self._state_history = self._state_history[-self._max_history:]

    def get_status(self) -> Dict:
        runtimes = list(self._runtimes.values())
        by_state = {}
        for rt in runtimes:
            s = rt.state.value
            by_state[s] = by_state.get(s, 0) + 1
        return {
            "globalState": self._global_state.value,
            "totalModules": len(runtimes),
            "byState": by_state,
            "healthy": sum(1 for rt in runtimes if rt.health_status),
            "startupOrder": self._startup_order,
        }

    def to_dict(self) -> Dict:
        return {
            "runtimes": [rt.to_dict() for rt in self._runtimes.values()],
            "status": self.get_status(),
        }
