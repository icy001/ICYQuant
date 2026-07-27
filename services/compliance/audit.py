from dataclasses import dataclass


@dataclass
class AuditRecord:
    record_id: str
    action: str
    result: str
    timestamp: int