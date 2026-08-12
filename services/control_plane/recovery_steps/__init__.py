"""
Recovery step executors.

Each executor implements exactly one :class:`StepType`.  Executors are
*coordinators*: they validate inputs, orchestrate optional injected domain
services (builders / stores / gates) and produce :class:`StepOutcome` with
:class:`RecoveryAction` requests.  They never modify business state directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryStep, StepOutcome, StepType


class StepExecutor(ABC):
    """Base class for recovery step executors."""

    step_type: StepType

    @abstractmethod
    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        """Run the step and return its outcome."""


#: registry of step executors (lazily imported to avoid import cycles)
EXECUTOR_TYPES: Dict[StepType, Any] = {}


def register_step_executor(cls: Any) -> Any:
    """Class decorator registering a :class:`StepExecutor` implementation."""
    if not getattr(cls, "step_type", None):
        raise ValueError(f"{cls.__name__} must declare a step_type")
    if cls.step_type in EXECUTOR_TYPES:
        raise ValueError(f"step type {cls.step_type!r} already registered")
    EXECUTOR_TYPES[cls.step_type] = cls
    return cls


_imported = False


def _import_executors() -> None:
    """Import every executor module once (idempotent)."""
    global _imported
    if _imported:
        return
    from . import (  # noqa: F401
        freeze_state,
        isolate_trading,
        rebuild_ledger,
        rebuild_position,
        reconcile_state,
        replay_events,
        resume_trading,
        verify_integrity,
    )
    _imported = True


def get_step_executor(step_type: StepType) -> StepExecutor:
    """Resolve the executor for a step type (lazy import)."""
    _import_executors()
    cls = EXECUTOR_TYPES.get(step_type)
    if cls is None:
        raise KeyError(f"no executor registered for step type {step_type!r}")
    return cls()


def registered_step_types() -> tuple:
    _import_executors()
    return tuple(sorted(EXECUTOR_TYPES, key=lambda s: s.value))


__all__ = [
    "StepExecutor",
    "EXECUTOR_TYPES",
    "register_step_executor",
    "get_step_executor",
    "registered_step_types",
]
