"""
Risk audit events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RiskAuditEvent:
    order_id: str
    account_id: str
    decision: str
    rule: str | None
    reason: str | None
    created_at: datetime