from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .level import EscalationLevel


@dataclass(frozen=True)
class EscalationDecision:
    should_escalate: bool
    current_level: EscalationLevel
    target_level: Optional[EscalationLevel]
    reason: str
    triggered_at: datetime
