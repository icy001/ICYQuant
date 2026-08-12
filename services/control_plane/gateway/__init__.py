"""
Institutional Control Gateway — the unified safety gate of the ICYQuant
trading execution path (Commit 26 Part 1.1).
"""

from __future__ import annotations

from .context import ControlContext, ControlRequest
from .decision import (
    ControlDecision,
    ControlDecisionReason,
)
from .errors import ControlEvaluationError, GatewayError
from .gateway import GatewayResult, InstitutionalControlGateway
from .policy import CONTROL_PRIORITY, GatewayPolicy
from .state import GatewayState

__all__ = [
    "CONTROL_PRIORITY",
    "ControlContext",
    "ControlDecision",
    "ControlDecisionReason",
    "ControlEvaluationError",
    "ControlRequest",
    "GatewayError",
    "GatewayPolicy",
    "GatewayResult",
    "GatewayState",
    "InstitutionalControlGateway",
]
