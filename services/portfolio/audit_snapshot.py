"""
Audit snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditSnapshot:

    total_records: int

    latest_action: str