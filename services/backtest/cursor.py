"""
Replay cursor.
"""

from dataclasses import dataclass


@dataclass
class ReplayCursor:
    position: int = 0

    def advance(self):
        self.position += 1