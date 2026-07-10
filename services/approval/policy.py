"""
Approval decision policy.

Determines whether a repair
requires human approval.
"""

from __future__ import annotations

from decimal import Decimal


class ApprovalPolicy:
    DEFAULT_THRESHOLD = Decimal(
        "1000"
    )

    def __init__(
        self,
        threshold=None,
    ):
        self.threshold = (
            threshold
            or
            self.DEFAULT_THRESHOLD
        )

    def require_approval(
        self,
        delta,
    ) -> bool:
        return abs(
            Decimal(
                str(delta)
            )
        ) > self.threshold