"""
ICYQuant Collaboration — comment service for research team collaboration.

Enables threaded discussions on research reports, hypotheses, evidence,
and notebooks within the research workspace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CommentTarget(str, Enum):
    REPORT = "report"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    NOTEBOOK = "notebook"
    EXPERIMENT = "experiment"
    GENERAL = "general"


@dataclass
class Comment:
    """A single comment in a research discussion."""
    comment_id: str
    target_type: CommentTarget
    target_id: str
    author_id: str
    content: str
    parent_comment_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    edited_at: Optional[datetime] = None
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class CommentService:
    """Threaded comment service for research collaboration.

    Supports:
        - Threaded comments with reply chains
        - Comments on any research artifact (report, hypothesis, notebook, etc.)
        - Comment resolution tracking
        - Author attribution and timestamps
    """

    def __init__(self) -> None:
        self._comments: dict[str, Comment] = {}
        self._thread_index: dict[str, list[str]] = {}  # target_id → comment_ids
        self._total_created = 0

    def add_comment(
        self,
        target_type: CommentTarget,
        target_id: str,
        author_id: str,
        content: str,
        parent_comment_id: str = "",
    ) -> Comment:
        """Add a comment to a research artifact."""
        import uuid
        comment = Comment(
            comment_id=str(uuid.uuid4()),
            target_type=target_type,
            target_id=target_id,
            author_id=author_id,
            content=content,
            parent_comment_id=parent_comment_id,
        )
        self._comments[comment.comment_id] = comment

        # Index by target
        if target_id not in self._thread_index:
            self._thread_index[target_id] = []
        self._thread_index[target_id].append(comment.comment_id)

        self._total_created += 1
        return comment

    def get_thread(self, target_id: str) -> list[Comment]:
        """Get all comments for a target, threaded."""
        comment_ids = self._thread_index.get(target_id, [])
        comments = [self._comments[cid] for cid in comment_ids if cid in self._comments]

        # Build thread tree
        root_comments = [c for c in comments if not c.parent_comment_id]
        root_comments.sort(key=lambda c: c.created_at)

        result: list[Comment] = []
        for root in root_comments:
            result.append(root)
            # Add replies
            replies = [c for c in comments if c.parent_comment_id == root.comment_id]
            replies.sort(key=lambda c: c.created_at)
            result.extend(replies)

        return result

    def resolve_comment(self, comment_id: str) -> bool:
        """Mark a comment as resolved."""
        comment = self._comments.get(comment_id)
        if comment:
            comment.resolved = True
            return True
        return False

    def edit_comment(self, comment_id: str, new_content: str) -> bool:
        """Edit an existing comment."""
        comment = self._comments.get(comment_id)
        if comment:
            comment.content = new_content
            comment.edited_at = datetime.now(timezone.utc)
            return True
        return False

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment and its replies."""
        comment = self._comments.pop(comment_id, None)
        if comment is None:
            return False
        # Remove from thread index
        if comment.target_id in self._thread_index:
            self._thread_index[comment.target_id] = [
                cid for cid in self._thread_index[comment.target_id] if cid != comment_id
            ]
        # Delete replies
        reply_ids = [cid for cid, c in self._comments.items() if c.parent_comment_id == comment_id]
        for rid in reply_ids:
            self.delete_comment(rid)
        return True

    def get_comment_count(self, target_id: str) -> int:
        """Get the number of comments for a target."""
        return len(self._thread_index.get(target_id, []))

    @property
    def total_created(self) -> int:
        return self._total_created
