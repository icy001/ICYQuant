from dataclasses import dataclass


@dataclass
class AuditEvent:
    event_id: str
    event_type: str
    actor: str
    payload: dict
