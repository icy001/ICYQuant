"""
Audit event definition.
"""


from dataclasses import dataclass


@dataclass
class AuditEvent:

    event_type: str

    timestamp: str

    payload: dict