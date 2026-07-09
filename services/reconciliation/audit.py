from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuditRecord:
    action: str
    symbol: str
    before: float
    after: float
    timestamp: datetime


class AuditTrail:
    def __init__(self) -> None:
        self.records: list = []

    def record(
        self,
        action: str,
        symbol: str,
        before: float,
        after: float,
    ) -> AuditRecord:
        record = AuditRecord(
            action=action,
            symbol=symbol,
            before=before,
            after=after,
            timestamp=datetime.utcnow(),
        )
        self.records.append(record)
        return record

    def get_records(self) -> list:
        return self.records
