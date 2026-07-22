"""
Recovery context.
"""

from dataclasses import dataclass


@dataclass
class RecoveryContext:

    workflow_id: str

    snapshot_id: str