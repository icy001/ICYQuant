"""
AdmissionEvidence — an immutable snapshot of why a final admission decision
was reached (spec section 13).

Every final decision produces one evidence record so that "why was this order
rejected?" can always be answered end to end:

    Request
      ↓
    Risk = APPROVED
      ↓
    Control = REDUCE_ONLY
      ↓
    Position Effect = INCREASE
      ↓
    Final = REJECTED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AdmissionEvidence:

    request_id: UUID

    risk_decision: str

    control_decision: str

    final_decision: str

    reason: str

    evidence_id: UUID = field(default_factory=uuid4)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
