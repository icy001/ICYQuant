"""
Execution verdicts — the possible outcomes of the combined
Execution → Venue → Routing evaluation (Commit 26 Part 1.4, spec section 26).

    ALLOW           primary execution/venue path is usable
    REDIRECT        primary venue blocked, a healthy fallback venue exists
    REDUCE_ONLY     new orders blocked, position reduction permitted
    CANCEL_ALLOWED  cancel is permitted while new orders are blocked
    EMERGENCY_ROUTE emergency flatten routed through a backup venue
    BLOCK           no usable path
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..routing.decision import RoutingDecision
from ..venue.decision import VenueControlDecision
from .decision import ExecutionControlDecision
from .request import ExecutionControlRequest


class ExecutionVerdict(str, Enum):

    ALLOW = "ALLOW"

    REDIRECT = "REDIRECT"

    REDUCE_ONLY = "REDUCE_ONLY"

    CANCEL_ALLOWED = "CANCEL_ALLOWED"

    BLOCK = "BLOCK"

    EMERGENCY_ROUTE = "EMERGENCY_ROUTE"


@dataclass(frozen=True)
class ExecutionResult:

    request: ExecutionControlRequest

    verdict: ExecutionVerdict

    execution_decision: ExecutionControlDecision

    venue_decision: VenueControlDecision

    routing_decision: RoutingDecision | None = None

    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict in {
            ExecutionVerdict.ALLOW,
            ExecutionVerdict.REDIRECT,
            ExecutionVerdict.REDUCE_ONLY,
            ExecutionVerdict.CANCEL_ALLOWED,
            ExecutionVerdict.EMERGENCY_ROUTE,
        }
