"""
ComponentState — per-service health state of the Control Plane.

Each component (Event Bus, Risk Engine, Execution Engine, Position Service, ...)
reports its own state.  These individual states are the raw inputs consumed by
the Control Plane evaluation pipeline:

    Component States
          |
          v
    Control Plane
          |
          v
    System / Trading / Operational State
"""

from __future__ import annotations

from enum import Enum


class ComponentState(str, Enum):
    """Health / lifecycle state of a single component."""

    STARTING = "STARTING"
    """Component is booting up and not yet serving traffic."""

    HEALTHY = "HEALTHY"
    """Component is fully operational and trusted."""

    DEGRADED = "DEGRADED"
    """Component is up but operating below nominal quality."""

    UNHEALTHY = "UNHEALTHY"
    """Component is up but explicitly reporting a health failure."""

    RECOVERING = "RECOVERING"
    """Component is executing a recovery / repair procedure."""

    STOPPED = "STOPPED"
    """Component was stopped intentionally."""

    UNKNOWN = "UNKNOWN"
    """No heartbeat received — liveness cannot be confirmed."""

    @property
    def is_healthy(self) -> bool:
        """Component is fully trusted."""
        return self is ComponentState.HEALTHY

    @property
    def is_available(self) -> bool:
        """Component can still participate in the trading core path."""
        return self in {
            ComponentState.STARTING,
            ComponentState.HEALTHY,
            ComponentState.DEGRADED,
            ComponentState.RECOVERING,
        }

    @property
    def is_degraded(self) -> bool:
        """Component is not contributing at full quality."""
        return self in {
            ComponentState.DEGRADED,
            ComponentState.UNHEALTHY,
            ComponentState.STOPPED,
            ComponentState.UNKNOWN,
        }
