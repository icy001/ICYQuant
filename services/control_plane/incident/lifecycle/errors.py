"""
Lifecycle layer errors.

``InvalidTransitionError`` lives in ``state_machine`` (per spec); the classes
below are the rest of the lifecycle error surface.
"""

from __future__ import annotations


class LifecycleError(Exception):
    """Base error for the incident lifecycle layer."""


class ActorRequiredError(LifecycleError):
    """Raised when an actor must be recorded for a transition."""


class ReasonRequiredError(LifecycleError):
    """Raised when a reason must be recorded for a transition."""


class StateConflictError(LifecycleError):
    """Raised when the target state conflicts with the current one."""
