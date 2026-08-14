"""
Risk policy evaluation trace (Commit 41 Part 1.3).

The trace is the audit record that answers the core Risk Engine question:

    "Why was this trade approved / rejected?"

It captures the outcome of every policy that was *actually executed*, in the
exact order the pipeline ran them, together with the final ``RiskDecision``.

Only executed policies appear in the trace.  A policy that was never run
(because an earlier policy already rejected the request) is NOT recorded as
``SKIPPED``: the audit trail never fabricates evaluations.

Status vocabulary:

- ``PASS``    : the policy ran and found the request acceptable
- ``REJECT``  : the policy ran and rejected the request
- ``SKIPPED`` : reserved for explicit short-circuit outcomes
- ``ERROR``   : the policy could not complete its evaluation (e.g. market
                data unavailable); the decision layer fails closed, but the
                trace keeps the error so the audit record is not corrupted
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STATUS_PASS = "PASS"
STATUS_REJECT = "REJECT"
STATUS_SKIPPED = "SKIPPED"
STATUS_ERROR = "ERROR"
#: Synthetic status used only by the replay comparator to express that a
#: policy exists in one trace but was not executed in the other.
STATUS_NOT_EXECUTED = "NOT_EXECUTED"

__all__ = [
    "STATUS_PASS",
    "STATUS_REJECT",
    "STATUS_SKIPPED",
    "STATUS_ERROR",
    "STATUS_NOT_EXECUTED",
    "PolicyEvaluationResult",
    "RiskPolicyTrace",
]


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Outcome of a single policy evaluation inside a trace."""

    policy_name: str
    status: str
    reason: Optional[str]
    evaluation_order: int


@dataclass(frozen=True)
class RiskPolicyTrace:
    """Immutable, ordered collection of policy evaluation results."""

    evaluations: tuple[PolicyEvaluationResult, ...]
