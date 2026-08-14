"""
Risk decision record model (Commit 41 Part 1.2 / 1.4).

``RiskDecision`` is the transient business result of a single evaluation.
``RiskDecisionRecord`` is the immutable, auditable persistence model.

A record is never mutated after it is stored; any correction must be
expressed as a new event / correction record.

Since Part 1.4 the record also persists:

- ``context_snapshot``: the complete decision-time inputs, so historical
  decisions can be deterministically replayed later.
- ``policy_version``: the policy set version used when the decision was made,
  so a replay can detect (and refuse to compare across) policy upgrades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..context_snapshot import RiskDecisionContextSnapshot
from ..policy_trace import RiskPolicyTrace


@dataclass(frozen=True)
class RiskDecisionRecord:
    decision_id: str
    request_id: str
    strategy_id: str
    instrument: str

    decision: str

    reason: str | None

    rejected_policy: str | None

    policy_trace: RiskPolicyTrace

    context_snapshot: RiskDecisionContextSnapshot

    policy_version: str

    created_at: datetime
