"""
Replay checkpoint model.

Large accounts may contain
millions of events.

Checkpoint allows:

Snapshot

+

Remaining Events
"""

from __future__ import annotations


from dataclasses import (
    dataclass,
)


from datetime import datetime


@dataclass(
    frozen=True,
)
class ReplayCheckpoint:
    """
    Replay progress marker.
    """

    event_count: int

    created_at: datetime