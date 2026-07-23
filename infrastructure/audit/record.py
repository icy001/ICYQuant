"""
Immutable audit record.
"""


from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRecord:

    actor: str

    action: str

    timestamp: str

    result: str