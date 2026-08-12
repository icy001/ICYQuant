"""Recovery decision (Commit 26 Part 1.5, spec section 13)."""

from dataclasses import dataclass

from .state import RecoveryState


@dataclass(frozen=True)
class RecoveryDecision:

    state: RecoveryState

    allow_resume: bool

    reason: str
