"""
Risk decision replay result (Commit 41 Part 1.4).

``RiskDecisionReplayResult`` is the immutable outcome of a deterministic
replay: it pairs the original decision with the replayed decision and lists
every concrete difference the comparator found.

The result never mutates the historical record — replay is verification, not
correction.
"""

from __future__ import annotations

from dataclasses import dataclass

from .policy_trace import RiskPolicyTrace


class ReplayStatus:
    """Outcome vocabulary for a replay.

    - ``MATCHED``    : replay completed and the re-evaluated decision matches
    - ``MISMATCHED`` : replay completed but the re-evaluated decision differs
    - ``FAILED``     : replay could not complete, so no verification happened
    """

    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RiskDecisionReplayResult:
    decision_id: str

    original_decision: str
    replayed_decision: str

    matched: bool

    original_policy_trace: RiskPolicyTrace
    replayed_policy_trace: RiskPolicyTrace

    differences: tuple[str, ...]

    @property
    def status(self) -> str:
        """``MATCHED`` when the decisions match, ``MISMATCHED`` otherwise."""
        if self.matched:
            return ReplayStatus.MATCHED
        return ReplayStatus.MISMATCHED


__all__ = [
    "ReplayStatus",
    "RiskDecisionReplayResult",
]
