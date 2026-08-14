"""
Risk decision replay audit record (Commit 41 Part 1.4).

A replay never rewrites the historical ``RiskDecisionRecord``; instead it
produces an append-only ``RiskDecisionReplayRecord`` so every verification
(even a failed one) is itself auditable:

    DEC-001
       |
       |-- REPLAY-001  MATCHED
       |-- REPLAY-002  MISMATCHED
       `-- REPLAY-003  FAILED
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RiskDecisionReplayRecord:
    replay_id: str
    decision_id: str

    original_decision: str
    replayed_decision: str

    status: str

    matched: bool

    differences: tuple[str, ...]

    replayed_at: datetime


__all__ = [
    "RiskDecisionReplayRecord",
]
