from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class AuditRecord:
    action: str
    symbol: str
    before: float
    after: float
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditTrail:
    def __init__(self) -> None:
        self.records: List[AuditRecord] = []

    def record(
        self,
        action: str,
        symbol: str,
        before: float,
        after: float,
        reason: str = "",
    ) -> AuditRecord:
        record = AuditRecord(
            action=action,
            symbol=symbol,
            before=before,
            after=after,
            reason=reason,
        )
        self.records.append(record)
        return record

    def get_records(self) -> List[AuditRecord]:
        return self.records

    def get_records_as_dict(self) -> List[dict]:
        return [record.to_dict() for record in self.records]
