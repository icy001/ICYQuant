"""
Risk decision trace (Commit 41 Part 1.5).

A trace answers the core Risk Decision question after the fact:

    Why was this request approved / rejected, and on which data?

It captures, for a single already-formed ``RiskDecision``:

- every rule that was *actually evaluated* (in pipeline order),
- every rule that *triggered* (rejected or failed to evaluate),
- the exact decision-time ``context_snapshot`` dict,
- the identity of the request, strategy and decision.

Design notes:

- The trace is immutable (``frozen=True``): once a decision is made, the
  historical trace records *why the system decided what it decided then*,
  not *what a re-computation would decide now*.  Position, PnL, market and
  limit changes after the fact must never rewrite a historical trace.
- The trace is produced *after* the decision.  It never re-runs Risk, so the
  audit trail can never diverge from the decision that was actually made.
- ``evaluated_rules`` and ``triggered_rules`` mirror the executed policy
  trace, so the trace is consistent with the persisted ``RiskPolicyTrace``
  instead of being recomputed independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..decision.risk_decision import RiskDecision


@dataclass(frozen=True)
class RiskDecisionTrace:
    """Immutable audit record for one already-formed risk decision."""

    decision_id: str
    request_id: str
    strategy_id: str

    decision: RiskDecision
    evaluated_rules: tuple[str, ...]

    triggered_rules: tuple[str, ...]

    context_snapshot: dict

    created_at: datetime


__all__ = [
    "RiskDecisionTrace",
]
