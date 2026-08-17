"""Transaction Flow Recovery Domain.

Part 1.5 of Commit 23: completes the self-healing pipeline by introducing
recovery jobs that replay immutable execution facts to restore Position and Ledger
state without direct state mutation.
"""

from .domain.recovery_job import RecoveryJob, RecoveryPlan, RecoveryJournal, RecoveryJournalEntry

from .event import EventRecord
from .manager import RecoveryManager
from .reader import EventReader
from .replay import ReplayEngine
from .repository import EventRepository
from .request import ReplayRequest
from .result import RecoveryResult
from .service import RecoveryService

__all__ = [
    "RecoveryJob",
    "RecoveryPlan",
    "RecoveryJournal",
    "RecoveryJournalEntry",
    # Legacy transaction-flow recovery API (module-level classes)
    "EventRecord",
    "EventReader",
    "EventRepository",
    "RecoveryManager",
    "RecoveryResult",
    "RecoveryService",
    "ReplayEngine",
    "ReplayRequest",
]
