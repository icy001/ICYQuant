"""
Tracing lifecycle hooks.

Provides a hook system that allows
external components to react to tracing
events such as span creation, completion,
and error conditions.

Hooks:
- before_request: Before HTTP request processing
- after_request: After HTTP request completion
- before_execute: Before business operation execution
- after_execute: After business operation completion
- before_publish: Before message publication
- after_publish: After message publication
- on_error: When an error occurs during operation
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class TraceHooks:
    """
    Tracing lifecycle hook manager.

    Allows registration of callback functions
    that are invoked at specific points in the
    tracing lifecycle, enabling custom behavior
    injection without modifying core tracing code.

    Hook Points:
    - before_request(span, request): Before HTTP processing
    - after_request(span, response): After HTTP completion
    - before_execute(span, operation): Before business op
    - after_execute(span, result): After business op
    - before_publish(span, message): Before message send
    - after_publish(span, message_id): After message send
    - before_consume(span, message): Before message consume
    - after_consume(span, result): After message consume
    - on_error(span, error): When error occurs
    - on_span_start(span): When a span is started
    - on_span_end(span): When a span is ended

    Usage:
        hooks = TraceHooks()

        def my_before_execute(span, operation):
            span.add_attribute("custom", "value")

        hooks.register("before_execute", my_before_execute)
        hooks.fire("before_execute", span, "risk.check")
    """

    HOOK_EVENTS = [
        "before_request",
        "after_request",
        "before_execute",
        "after_execute",
        "before_publish",
        "after_publish",
        "before_consume",
        "after_consume",
        "on_error",
        "on_span_start",
        "on_span_end",
    ]

    def __init__(
        self,
    ) -> None:
        """Initialize hook manager."""

        self._hooks: Dict[str, List[Callable]] = {
            event: [] for event in self.HOOK_EVENTS
        }

    def register(
        self,
        event: str,
        callback: Callable,
    ) -> None:
        """
        Register a hook callback.

        Args:
            event: Hook event name.
            callback: Callback function.

        Raises:
            ValueError: If event is not valid.
        """

        if event not in self._hooks:
            raise ValueError(
                f"Unknown hook event: {event}. "
                f"Valid events: {', '.join(self.HOOK_EVENTS)}"
            )
        self._hooks[event].append(callback)

    def unregister(
        self,
        event: str,
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Unregister a hook callback.

        Args:
            event: Hook event name.
            callback: Specific callback to remove. If None, removes all.
        """

        if event not in self._hooks:
            return

        if callback is None:
            self._hooks[event].clear()
        elif callback in self._hooks[event]:
            self._hooks[event].remove(callback)

    def fire(
        self,
        event: str,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Fire a hook event.

        Executes all registered callbacks
        for the given event, collecting their
        return values.

        Args:
            event: Hook event name.
            *args: Positional arguments for callbacks.
            **kwargs: Keyword arguments for callbacks.

        Returns:
            List of callback return values.
        """

        if event not in self._hooks:
            return []

        results = []
        for callback in self._hooks[event]:
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception:
                pass
        return results

    def fire_async(
        self,
        event: str,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Fire a hook event (async-compatible).

        Same as fire() but designed for async
        contexts. Callbacks should be sync or
        use run_in_executor pattern.

        Args:
            event: Hook event name.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            List of callback return values.
        """

        return self.fire(event, *args, **kwargs)

    def get_hooks(
        self,
        event: str,
    ) -> List[Callable]:
        """Get all hooks for an event."""
        return list(self._hooks.get(event, []))

    def clear(
        self,
    ) -> None:
        """Clear all hooks."""
        for event in self._hooks:
            self._hooks[event].clear()

    def get_status(
        self,
    ) -> Dict[str, int]:
        """Get hook registration status."""
        return {
            event: len(hooks)
            for event, hooks in self._hooks.items()
            if hooks
        }


# Global hook instance
_global_hooks: Optional[TraceHooks] = None


def get_hooks() -> TraceHooks:
    """Get the global trace hooks instance."""
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = TraceHooks()
    return _global_hooks


def register_hook(event: str, callback: Callable) -> None:
    """Register a callback on the global hook instance."""
    get_hooks().register(event, callback)


def fire_hook(event: str, *args: Any, **kwargs: Any) -> List[Any]:
    """Fire a hook on the global instance."""
    return get_hooks().fire(event, *args, **kwargs)
