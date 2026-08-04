"""Plugin lifecycle manager.

Manages plugin lifecycle state transitions with hooks.
States: REGISTERED -> LOADED -> INITIALIZED -> RUNNING -> STOPPED -> UNINSTALLED.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .hooks import HookRegistry
from .models import PluginState

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: Dict[PluginState, List[PluginState]] = {
    PluginState.REGISTERED: [PluginState.LOADED],
    PluginState.LOADED: [PluginState.INITIALIZED, PluginState.FAILED],
    PluginState.INITIALIZED: [PluginState.RUNNING, PluginState.FAILED],
    PluginState.RUNNING: [PluginState.STOPPED, PluginState.FAILED],
    PluginState.STOPPED: [PluginState.UNINSTALLED, PluginState.LOADED],
    PluginState.FAILED: [PluginState.REGISTERED, PluginState.LOADED, PluginState.UNINSTALLED],
    PluginState.UNINSTALLED: [],
}


class PluginLifecycle:
    """Manages plugin lifecycle state transitions.

    States: REGISTERED -> LOADED -> INITIALIZED -> RUNNING -> STOPPED -> UNINSTALLED
    Each transition triggers appropriate hooks.
    """

    def __init__(self, hooks: Any = None) -> None:
        self._states: Dict[str, PluginState] = {}
        self._plugins: Dict[str, Any] = {}
        self._hooks: HookRegistry = hooks if hooks is not None else HookRegistry()
        self._transition_log: List[Dict[str, Any]] = []

    def register(self, plugin_id: str, plugin: Any = None) -> None:
        self._states[plugin_id] = PluginState.REGISTERED
        if plugin is not None:
            self._plugins[plugin_id] = plugin

    async def transition_to(
        self, plugin_id: str, target_state: PluginState, plugin: Any = None
    ) -> Dict[str, Any]:
        current = self._states.get(plugin_id, PluginState.REGISTERED)
        if not self.can_transition(current, target_state):
            result: Dict[str, Any] = {
                "success": False,
                "plugin_id": plugin_id,
                "from": current.value,
                "to": target_state.value,
                "error": f"Cannot transition from {current.value} to {target_state.value}",
            }
            self._transition_log.append(result)
            return result
        before_hook = f"before_{target_state.value}"
        after_hook = f"after_{target_state.value}"
        try:
            await self._hooks.execute(before_hook, plugin_id, plugin)
        except Exception as e:
            logger.error("Before-hook failed for %s: %s", plugin_id, e)
            result = {
                "success": False,
                "plugin_id": plugin_id,
                "from": current.value,
                "to": target_state.value,
                "error": str(e),
            }
            self._transition_log.append(result)
            return result
        self._states[plugin_id] = target_state
        if plugin is not None and hasattr(plugin, "state"):
            try:
                plugin.state = target_state
            except Exception:
                pass
        if plugin is not None:
            self._invoke_plugin_hook(plugin, target_state)
        try:
            await self._hooks.execute(after_hook, plugin_id, plugin)
        except Exception as e:
            logger.error("After-hook failed for %s: %s", plugin_id, e)
        result = {
            "success": True,
            "plugin_id": plugin_id,
            "from": current.value,
            "to": target_state.value,
        }
        self._transition_log.append(result)
        logger.info(
            "Plugin '%s' transitioned: %s -> %s",
            plugin_id,
            current.value,
            target_state.value,
        )
        return result

    async def initialize(
        self, plugin_id: str, plugin: Any = None
    ) -> Dict[str, Any]:
        current = self._states.get(plugin_id, PluginState.REGISTERED)
        steps: List[PluginState] = []
        if current == PluginState.REGISTERED:
            steps = [PluginState.LOADED, PluginState.INITIALIZED, PluginState.RUNNING]
        elif current == PluginState.LOADED:
            steps = [PluginState.INITIALIZED, PluginState.RUNNING]
        elif current == PluginState.INITIALIZED:
            steps = [PluginState.RUNNING]
        elif current == PluginState.RUNNING:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is already running.",
            }
        elif current == PluginState.STOPPED:
            steps = [PluginState.LOADED, PluginState.INITIALIZED, PluginState.RUNNING]
        elif current == PluginState.FAILED:
            steps = [PluginState.LOADED, PluginState.INITIALIZED, PluginState.RUNNING]
        else:
            return {
                "success": False,
                "plugin_id": plugin_id,
                "error": f"Cannot initialize from state: {current.value}",
            }
        last_result: Dict[str, Any] = {}
        for step in steps:
            last_result = await self.transition_to(plugin_id, step, plugin)
            if not last_result.get("success"):
                return last_result
        return last_result

    async def start(
        self, plugin_id: str, plugin: Any = None
    ) -> Dict[str, Any]:
        current = self._states.get(plugin_id, PluginState.REGISTERED)
        if current == PluginState.RUNNING:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is already running.",
            }
        if current == PluginState.REGISTERED:
            return await self.initialize(plugin_id, plugin)
        if current == PluginState.STOPPED:
            return await self.transition_to(plugin_id, PluginState.LOADED, plugin)
        if current in (PluginState.LOADED, PluginState.INITIALIZED, PluginState.FAILED):
            return await self.initialize(plugin_id, plugin)
        return {
            "success": False,
            "plugin_id": plugin_id,
            "error": f"Cannot start from state: {current.value}",
        }

    async def stop(
        self, plugin_id: str, plugin: Any = None
    ) -> Dict[str, Any]:
        current = self._states.get(plugin_id, PluginState.REGISTERED)
        if current == PluginState.STOPPED:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is already stopped.",
            }
        if current != PluginState.RUNNING:
            return {
                "success": False,
                "plugin_id": plugin_id,
                "error": f"Cannot stop from state: {current.value} (must be RUNNING)",
            }
        return await self.transition_to(plugin_id, PluginState.STOPPED, plugin)

    async def shutdown(
        self, plugin_id: str, plugin: Any = None
    ) -> Dict[str, Any]:
        current = self._states.get(plugin_id, PluginState.REGISTERED)
        if current == PluginState.UNINSTALLED:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is already uninstalled.",
            }
        if current == PluginState.RUNNING:
            stop_result = await self.transition_to(plugin_id, PluginState.STOPPED, plugin)
            if not stop_result.get("success"):
                return stop_result
        return await self.transition_to(plugin_id, PluginState.UNINSTALLED, plugin)

    def can_transition(self, current: PluginState, target: PluginState) -> bool:
        if current == target:
            return True
        valid_next = VALID_TRANSITIONS.get(current, [])
        return target in valid_next

    def get_state(self, plugin_id: str) -> PluginState:
        return self._states.get(plugin_id, PluginState.REGISTERED)

    def get_all_states(self) -> Dict[str, PluginState]:
        return dict(self._states)

    def get_stats(self) -> Dict[str, Any]:
        state_counts: Dict[str, int] = {}
        for state in self._states.values():
            key = state.value
            state_counts[key] = state_counts.get(key, 0) + 1
        return {
            "total_plugins": len(self._states),
            "by_state": state_counts,
            "transition_count": len(self._transition_log),
            "hooks_registered": self._count_hooks(),
        }

    def _count_hooks(self) -> int:
        from .hooks import HookPoint
        total = 0
        for attr_name in dir(HookPoint):
            if attr_name.startswith("_"):
                continue
            hook_point = getattr(HookPoint, attr_name)
            hooks = self._hooks.get_hooks(hook_point)
            total += len(hooks)
        return total

    @staticmethod
    def _invoke_plugin_hook(plugin: Any, state: PluginState) -> None:
        method_map: Dict[str, str] = {
            PluginState.LOADED: "on_load",
            PluginState.INITIALIZED: "on_init",
            PluginState.RUNNING: "on_start",
            PluginState.STOPPED: "on_stop",
            PluginState.UNINSTALLED: "on_unload",
            PluginState.FAILED: "on_fail",
        }
        method_name = method_map.get(state)
        if method_name is None:
            return
        method = getattr(plugin, method_name, None)
        if callable(method):
            try:
                method()
            except Exception as e:
                logger.error(
                    "Plugin hook '%s' failed for '%s': %s",
                    method_name,
                    getattr(plugin, "id", str(plugin)),
                    e,
                )