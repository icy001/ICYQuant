"""
Consensus record model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConsensusRecord:

    consensus_id: str

    term: int

    leader_id: str

    committed_at: datetime

    payload: dict