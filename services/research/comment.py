"""
Research comment.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Comment:

    comment_id: str

    author: str

    content: str

    created_at: datetime