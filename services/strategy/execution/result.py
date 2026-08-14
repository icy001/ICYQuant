"""Outcome of an intent creation attempt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IntentResult:
    """Outcome of a single intent creation attempt.

    ``accepted=True`` with ``state=PENDING`` means the intent entered the
    pipeline; ``accepted=False`` with ``state=REJECTED`` means the boundary
    refused it.  ``reason`` names the exact gate that refused it
    (``session_not_active``, ``readiness_blocked``, a validation error, ...).
    """

    intent_id: str
    strategy_id: str
    signal_id: str

    accepted: bool

    state: str

    reason: Optional[str] = None
