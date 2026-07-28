from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Decision:
    """Represents a quant trading decision based on fused signals and risk assessment."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    score: float
    status: str = "PENDING"
    decision_id: str = ""
    reason: str = ""
    signals: Dict[str, float] = field(default_factory=dict)
    risk_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def approve(self) -> None:
        self.status = "APPROVED"
        self.approved_at = datetime.utcnow()

    def reject(self, reason: str = "") -> None:
        self.status = "REJECTED"
        if reason:
            self.reason = reason

    def execute(self) -> None:
        self.status = "EXECUTED"
        self.executed_at = datetime.utcnow()

    def is_actionable(self) -> bool:
        return self.status in ("APPROVED",) and self.score > 0
