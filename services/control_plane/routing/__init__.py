"""
Routing Control — venue selection with explicit failover
(Commit 26 Part 1.4).

Only venues whose Venue Control explicitly allows new orders can be
selected; a failed primary venue is redirected to a healthy fallback and
the redirect is recorded in the audit trail.
"""

from .controller import RoutingController
from .decision import RoutingDecision
from .policy import RoutingPolicy

__all__ = [
    "RoutingController",
    "RoutingDecision",
    "RoutingPolicy",
]
