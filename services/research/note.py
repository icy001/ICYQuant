"""
Research note.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchNote:
    note_id: str
    content: str