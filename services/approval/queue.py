"""
Approval queue.

Temporary in-memory implementation.

Future:

- PostgreSQL
- Redis
- Message Queue
"""

from __future__ import annotations

from .model import (
    ApprovalRequest,
)


class ApprovalQueue:
    def __init__(self):
        self.requests = []

    def add(
        self,
        request: ApprovalRequest,
    ):
        self.requests.append(
            request
        )

    def pending(
        self,
    ):
        return [
            r
            for r in self.requests
            if r.status.value
            ==
            "PENDING"
        ]