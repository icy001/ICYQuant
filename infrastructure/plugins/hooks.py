from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import inspect
import logging

logger = logging.getLogger(__name__)

HookType = Callable[..., Any]


class HookPoint:
    """String constants identifying plugin lifecycle hook points."""

    BEFORE_INSTALL = "before_install"
    AFTER_INSTALL = "after_install"
    BEFORE_LOAD = "before_load"
    AFTER_LOAD = "after_load"
    BEFORE_INIT = "before_init"
    AFTER_INIT = "after_init"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    BEFORE_STOP = "before_stop"
    AFTER_STOP = "after_stop"
    BEFORE_UNLOAD = "before_unload"
    AFTER_UNLOAD = "after_unload"


class HookRegistry:
    """Registry for plugin lifecycle hooks."""

    def __init__(self) -> None:
        self._hooks: Dict[str, List[tuple]] = {}

    def register(self, hook_point: str, callback: HookType, priority: int = 0) -> None:
        hooks = self._hooks.setdefault(hook_point, [])
        hooks.append((priority, callback))
        # Stable sort by priority ascending: lower priority runs first.
        hooks.sort(key=lambda item: item[0])

    def unregister(self, hook_point: str, callback: HookType) -> None:
        hooks = self._hooks.get(hook_point, [])
        remaining = [h for h in hooks if h[1] is not callback]
        if remaining:
            self._hooks[hook_point] = remaining
        else:
            self._hooks.pop(hook_point, None)

    def get_hooks(self, hook_point: str) -> List[tuple]:
        """Return ``[(priority, callback)]`` sorted by priority."""
        return list(self._hooks.get(hook_point, []))

    async def execute(self, hook_point: str, *args: Any, **kwargs: Any) -> List[Any]:
        results: List[Any] = []
        for _priority, callback in self.get_hooks(hook_point):
            try:
                result = callback(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                results.append(result)
            except Exception:
                logger.exception("Hook %s failed", hook_point)
                results.append(None)
        return results

    def clear(self, hook_point: str = None) -> None:
        if hook_point is None:
            self._hooks.clear()
        else:
            self._hooks.pop(hook_point, None)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for hook_point, hooks in self._hooks.items():
            entries = []
            for priority, callback in hooks:
                name = getattr(callback, "__name__", None) or repr(callback)
                entries.append({"priority": priority, "callback": name})
            result[hook_point] = entries
        return result
