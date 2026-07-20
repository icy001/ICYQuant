"""
Replay clock.
"""

from datetime import datetime


class ReplayClock:
    def now(self) -> datetime:
        return datetime.utcnow()