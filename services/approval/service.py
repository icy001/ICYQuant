"""
Approval service.

Controls repair execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .model import (
    ApprovalRequest,
    ApprovalStatus,
)


class ApprovalService:
    def __init__(
        self,
        queue,
    ):
        self.queue = queue

    def create_request(
        self,
        action,
        payload,
        reason,
    ):
        request = ApprovalRequest(
            request_id=uuid4(),
            action=action,
            payload=payload,
            reason=reason,
            status=
            ApprovalStatus.PENDING,
            created_at=datetime.now(
                timezone.utc
            )
        )

        self.queue.add(
            request
        )

        return request