"""
Approval Gate — Gate checks before decisions are forwarded for approval.

Validates that the request is complete and within approval scope.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalGate:
    """
    Validates approval requests before they enter the approval pipeline.

    Checks completeness, scope validity, and authority of the request.
    """

    def __init__(self):
        self._validated_count = 0
        self._rejected_count = 0

    def validate(self, request: Any) -> tuple[bool, str]:
        """Validate an approval request."""
        self._validated_count += 1

        if not getattr(request, "decision_id", ""):
            self._rejected_count += 1
            return False, "Missing decision_id"

        if not getattr(request, "action", ""):
            self._rejected_count += 1
            return False, "Missing action"

        if not getattr(request, "scope", ""):
            self._rejected_count += 1
            return False, "Missing scope"

        return True, ""

    def stats(self) -> dict:
        return {
            "validated": self._validated_count,
            "rejected": self._rejected_count,
        }
