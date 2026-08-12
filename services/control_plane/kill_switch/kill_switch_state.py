"""
KillSwitchState — lifecycle of a single scoped kill switch.

    INACTIVE   normal operation
    ARMED      primed but not yet blocking
    ACTIVE     blocking — new instructions matching this scope are DENY
    RELEASING  release requested; revalidation in progress

Release is never a single hop ACTIVE → INACTIVE: the switch goes through
RELEASING and only returns to INACTIVE after the release preconditions
(system READY, risk/execution/event-bus HEALTHY, data FRESH ...) pass.
"""

from __future__ import annotations

from enum import Enum


class KillSwitchState(str, Enum):
    INACTIVE = "INACTIVE"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    RELEASING = "RELEASING"

    @property
    def is_blocking(self) -> bool:
        """States that still deny matching trading instructions."""
        return self is KillSwitchState.ACTIVE or self is KillSwitchState.RELEASING
