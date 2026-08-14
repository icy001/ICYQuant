"""Strategy runtime adapter.

The strategy domain must never depend on the concrete runtime technology
(Docker, Kubernetes, a local process, a thread, a broker or the OMS).
Every lifecycle action is executed through ``StrategyRuntimeAdapter``::

    Strategy
        |
        v
    StrategyRuntimeAdapter   <- this module (the seam)
        |
        v
    Actual Runtime (process / container / worker / ...)

The adapter also owns the resume pre-flight checks (strategy config,
market data, risk gate, execution connectivity) required before a paused
strategy may re-enter the ``RUNNING`` control state.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class RuntimeActionError(RuntimeError):
    """Raised by an adapter when a lifecycle action failed at the runtime.

    The orchestrator converts this into a ``FAILED`` control state; it must
    never pretend the action succeeded.
    """


@runtime_checkable
class StrategyRuntimeAdapter(Protocol):
    """The technology-neutral seam between strategy control and runtime."""

    def start(self, strategy_id: str) -> None:  # pragma: no cover
        """Ask the runtime to bring the strategy process up."""
        ...

    def pause(self, strategy_id: str) -> None:  # pragma: no cover
        """Disable signal generation; the process stays healthy."""
        ...

    def resume(self, strategy_id: str) -> None:  # pragma: no cover
        """Re-enable signal generation after a pause."""
        ...

    def stop(self, strategy_id: str) -> None:  # pragma: no cover
        """Graceful shutdown: flush, cleanup, persist, close."""
        ...

    def kill(self, strategy_id: str) -> None:  # pragma: no cover
        """Immediate termination; graceful shutdown is not guaranteed."""
        ...

    def can_resume(self, strategy_id: str) -> bool:  # pragma: no cover
        """Resume pre-flight checks (config / market data / risk gate /
        execution connectivity).  ``False`` means the strategy must not
        return to ``RUNNING``.
        """
        ...

    def get_state(self, strategy_id: str) -> str:  # pragma: no cover
        """Return the current :class:`RuntimeState` value."""
        ...
