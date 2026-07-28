from dataclasses import dataclass


@dataclass
class AuditEvent:
    event_id: str
    user_id: str
    action: str
    resource: str
    timestamp: int
    result: str