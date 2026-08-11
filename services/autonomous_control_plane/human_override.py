"""
Human Override — Human intervention in autonomous decisions.

Allows operators to override autonomous decisions with full audit
trail of who, what, when, why, and impact.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HumanOverride:
    """
    Manages human overrides of autonomous decisions.

    All overrides are recorded with operator identity, timestamp,
    reason, scope, and before/after state for full auditability.
    """

    VALID_ACTIONS = {
        "APPROVE", "REJECT", "PAUSE", "RESUME",
        "REDUCE_RISK", "FORCE_QUARANTINE", "ROLLBACK", "HALT",
    }

    def __init__(self):
        self._overrides: list[dict] = []

    def apply(
        self,
        decision_id: str,
        action: str,
        operator: str,
        reason: str,
        previous_state: Optional[dict] = None,
        scope: str = "global",
    ) -> tuple[bool, str]:
        """
        Apply a human override to an autonomous decision.

        Returns (success, message).
        """
        if action not in self.VALID_ACTIONS:
            return False, f"Invalid override action: {action}"

        override_record = {
            "decision_id": decision_id,
            "action": action,
            "operator": operator,
            "reason": reason,
            "scope": scope,
            "previous_state": previous_state,
            "new_state": {"action": action, "reason": reason},
            "timestamp": time.time(),
        }

        self._overrides.append(override_record)
        logger.warning(
            "HUMAN OVERRIDE: decision=%s action=%s operator=%s reason=%s",
            decision_id, action, operator, reason,
        )

        return True, ""

    def history(self, operator: Optional[str] = None) -> list[dict]:
        """Get override history, optionally filtered by operator."""
        if operator:
            return [o for o in self._overrides if o["operator"] == operator]
        return list(self._overrides)

    def stats(self) -> dict:
        actions = {}
        for o in self._overrides:
            actions[o["action"]] = actions.get(o["action"], 0) + 1
        return {
            "overrides_total": len(self._overrides),
            "by_action": actions,
        }
