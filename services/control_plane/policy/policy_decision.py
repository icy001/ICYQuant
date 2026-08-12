"""
PolicyDecision — the operational outcome of a Policy Evaluation.

A Policy Decision is NOT the final Trading Gate decision.  Policy answers:

    "what operational action should the system take?"

The Trading Gate answers:

    "may this specific order proceed?"

So the Policy Engine can say HALT while the Gate still evaluates individual
orders — usually resulting in DENY.

Fail-safe ordering (safety first):

    ALLOW < DEGRADE < RECOVER < BLOCK < HALT < ESCALATE

When several policies disagree (A→ALLOW, B→DEGRADE, C→HALT) the engine
always resolves to the most severe one (HALT).
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, List


class PolicyDecision(str, Enum):
    """Operational decision produced by the Policy Engine."""

    ALLOW = "ALLOW"
    DEGRADE = "DEGRADE"
    RECOVER = "RECOVER"
    BLOCK = "BLOCK"
    HALT = "HALT"
    ESCALATE = "ESCALATE"


#: Fail-safe severity rank.  Higher is more restrictive.
FAIL_SAFE_RANK: Dict[PolicyDecision, int] = {
    PolicyDecision.ALLOW: 0,
    PolicyDecision.DEGRADE: 1,
    PolicyDecision.RECOVER: 2,
    PolicyDecision.BLOCK: 3,
    PolicyDecision.HALT: 4,
    PolicyDecision.ESCALATE: 5,
}


def is_at_least(decision: PolicyDecision, floor: PolicyDecision) -> bool:
    """True when ``decision`` is at least as severe as ``floor``."""
    return FAIL_SAFE_RANK[decision] >= FAIL_SAFE_RANK[floor]


def is_more_severe(a: PolicyDecision, b: PolicyDecision) -> bool:
    """True when ``a`` is strictly more severe than ``b``."""
    return FAIL_SAFE_RANK[a] > FAIL_SAFE_RANK[b]


def most_severe(decisions: Iterable[PolicyDecision]) -> PolicyDecision:
    """
    Resolve a set of decisions to the single most severe one (fail-safe).

    Empty input → ALLOW (nothing fired).
    """
    values = list(decisions)
    if not values:
        return PolicyDecision.ALLOW
    return max(values, key=lambda d: FAIL_SAFE_RANK[d])


def sorted_by_severity(
    decisions: Iterable[PolicyDecision],
) -> List[PolicyDecision]:
    """Decisions ordered most-severe first (deterministic)."""
    return sorted(decisions, key=lambda d: FAIL_SAFE_RANK[d], reverse=True)
