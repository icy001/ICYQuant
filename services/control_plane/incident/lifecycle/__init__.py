"""Incident Lifecycle — auditable state transitions and lifecycle service.

NOTE: ``IncidentLifecycleService`` is intentionally NOT re-exported here to
avoid an import cycle (it imports the ``Incident`` aggregate, which itself
imports ``IncidentTransition`` from this package). Import it directly from
``.service`` instead.
"""

from .errors import (
    ActorRequiredError,
    LifecycleError,
    ReasonRequiredError,
    StateConflictError,
)
from .state_machine import (
    IncidentState,
    IncidentStateMachine,
    InvalidTransitionError,
)
from .transition import IncidentTransition

__all__ = [
    "ActorRequiredError",
    "IncidentState",
    "IncidentStateMachine",
    "IncidentTransition",
    "InvalidTransitionError",
    "LifecycleError",
    "ReasonRequiredError",
    "StateConflictError",
]
