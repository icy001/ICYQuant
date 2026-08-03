"""
Tracing decorators.

Provides decorators for automatically
creating spans around business methods,
eliminating boilerplate tracing code.

Usage:
    from infrastructure.tracing.decorators import traced

    @traced("risk.check")
    def check_risk(order_id: str):
        # Span automatically created
        ...

    @traced("order.submit", kind="client")
    async def submit_order(order: dict):
        # Async support
        ...

    @traced("strategy.execute", attributes={"strategy.id": "grid"})
    def execute_strategy():
        # Pre-set attributes
        ...
"""

from __future__ import annotations

import asyncio
import functools
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .context import current_span, set_span, span_context
from .hooks import fire_hook, get_hooks
from .models import SpanKind, SpanStatus
from .tracer import Tracer


def traced(
    operation: str,
    kind: str = "internal",
    attributes: Optional[Dict[str, Any]] = None,
    tracer: Optional[Tracer] = None,
    capture_args: bool = False,
    capture_result: bool = False,
    stack_level: int = 1,
) -> Callable:
    """
    Decorator to create a span around a function.

    Automatically creates and manages a span
    for the decorated function, handling
    start/finish lifecycle and error capture.

    Args:
        operation: Span operation name.
        kind: Span kind (internal, server, client, producer, consumer).
        attributes: Pre-set span attributes.
        tracer: Optional Tracer instance.
        capture_args: Whether to capture function args as attributes.
        capture_result: Whether to capture return value as attribute.
        stack_level: Stack level for caller info.

    Returns:
        Decorated function wrapper.

    Usage:
        @traced("risk.check")
        def check_risk(order_id):
            ...

        @traced("order.submit", kind="client")
        async def submit_order(order):
            ...
    """

    kind_map = {
        "internal": SpanKind.INTERNAL,
        "server": SpanKind.SERVER,
        "client": SpanKind.CLIENT,
        "producer": SpanKind.PRODUCER,
        "consumer": SpanKind.CONSUMER,
    }
    span_kind = kind_map.get(kind, SpanKind.INTERNAL)

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            return _wrap_async(
                func, operation, span_kind, attributes,
                tracer, capture_args, capture_result,
            )
        else:
            return _wrap_sync(
                func, operation, span_kind, attributes,
                tracer, capture_args, capture_result,
            )

    return decorator


def _wrap_sync(
    func: Callable,
    operation: str,
    kind: SpanKind,
    attributes: Optional[Dict[str, Any]],
    tracer: Optional[Tracer],
    capture_args: bool,
    capture_result: bool,
) -> Callable:
    """Wrap a synchronous function with span creation."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        _tracer = tracer or Tracer()
        span = _tracer.start_span(
            operation=operation,
            kind=kind,
            attributes=attributes,
        )

        # Fire hooks
        hooks = get_hooks()
        hooks.fire("on_span_start", span)
        hooks.fire("before_execute", span, operation)

        # Capture args if configured
        if capture_args:
            _capture_args(span, func, args, kwargs)

        start_time = datetime.utcnow()

        try:
            result = func(*args, **kwargs)

            # Capture result if configured
            if capture_result:
                span.add_attribute(
                    f"{operation}.result",
                    str(result)[:256] if result else None,
                )

            # Set success status
            span.set_status(SpanStatus.OK)
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            span.add_attribute("icyquant.latency.ms", round(duration, 2))

            # Fire hooks
            hooks.fire("after_execute", span, result)
            hooks.fire("on_span_end", span)

            _tracer.finish_span(span, status=SpanStatus.OK)
            return result

        except Exception as exc:
            # Set error status
            span.set_status(SpanStatus.ERROR)
            span.add_attribute("exception.type", type(exc).__name__)
            span.add_attribute("exception.message", str(exc))

            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            span.add_attribute("icyquant.latency.ms", round(duration, 2))

            # Fire hooks
            hooks.fire("on_error", span, exc)
            hooks.fire("after_execute", span, None)
            hooks.fire("on_span_end", span)

            _tracer.finish_span(span, status=SpanStatus.ERROR)
            raise

    return wrapper


def _wrap_async(
    func: Callable,
    operation: str,
    kind: SpanKind,
    attributes: Optional[Dict[str, Any]],
    tracer: Optional[Tracer],
    capture_args: bool,
    capture_result: bool,
) -> Callable:
    """Wrap an async function with span creation."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        _tracer = tracer or Tracer()
        span = _tracer.start_span(
            operation=operation,
            kind=kind,
            attributes=attributes,
        )

        # Fire hooks
        hooks = get_hooks()
        hooks.fire("on_span_start", span)
        hooks.fire("before_execute", span, operation)

        # Capture args if configured
        if capture_args:
            _capture_args(span, func, args, kwargs)

        start_time = datetime.utcnow()

        try:
            result = await func(*args, **kwargs)

            # Capture result if configured
            if capture_result:
                span.add_attribute(
                    f"{operation}.result",
                    str(result)[:256] if result else None,
                )

            span.set_status(SpanStatus.OK)
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            span.add_attribute("icyquant.latency.ms", round(duration, 2))

            hooks.fire("after_execute", span, result)
            hooks.fire("on_span_end", span)

            _tracer.finish_span(span, status=SpanStatus.OK)
            return result

        except Exception as exc:
            span.set_status(SpanStatus.ERROR)
            span.add_attribute("exception.type", type(exc).__name__)
            span.add_attribute("exception.message", str(exc))

            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            span.add_attribute("icyquant.latency.ms", round(duration, 2))

            hooks.fire("on_error", span, exc)
            hooks.fire("after_execute", span, None)
            hooks.fire("on_span_end", span)

            _tracer.finish_span(span, status=SpanStatus.ERROR)
            raise

    return wrapper


def _capture_args(
    span: Any,
    func: Callable,
    args: tuple,
    kwargs: dict,
) -> None:
    """Capture function arguments as span attributes."""

    import inspect
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        for name, value in bound.arguments.items():
            if name in ("self", "cls"):
                continue
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 256:
                str_value = str_value[:256] + "..."
            span.add_attribute(f"arg.{name}", str_value)
    except (ValueError, TypeError):
        pass


def traced_class(
    operation_prefix: str = "",
    kind: str = "internal",
    attributes: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Class decorator to trace all public methods.

    Usage:
        @traced_class(operation_prefix="risk")
        class RiskService:
            def check(self, order_id):
                # Automatically traced as "risk.check"
                ...
    """

    def decorator(cls: type) -> type:
        for name, method in list(cls.__dict__.items()):
            if name.startswith("_") or not callable(method):
                continue

            op_name = f"{operation_prefix}.{name}" if operation_prefix else name
            setattr(
                cls, name,
                traced(
                    operation=op_name,
                    kind=kind,
                    attributes=attributes,
                )(method),
            )
        return cls

    return decorator
