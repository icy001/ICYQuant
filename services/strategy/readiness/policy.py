"""Strategy execution readiness policy.

Different strategies can own different readiness policies.  A policy decides
which checks are mandatory (``require_*``) and whether a degraded strategy
may still attempt to trade (``allow_degraded``).  The lifecycle gate is
always mandatory and cannot be switched off.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessPolicy:
    """Per-strategy switches controlling which readiness checks are mandatory."""

    require_runtime: bool = True
    require_market_data: bool = True
    require_configuration: bool = True
    require_risk: bool = True
    require_execution: bool = True

    allow_degraded: bool = False

    def requires(self, check_name: str) -> bool:
        """Return True when the check ``check_name`` is mandatory.

        Unknown check names (e.g. ``lifecycle``) default to required so a
        missing switch can never silently disable a gate.
        """
        switch = getattr(self, f"require_{check_name}", None)
        if switch is None:
            return True
        return bool(switch)
