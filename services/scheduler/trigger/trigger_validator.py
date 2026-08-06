"""Trigger Validator — validates trigger configurations before registration.

Checks:
* Cron expression syntax and bounds
* Interval sanity (non-negative, reasonable range)
* Calendar market/session validity
* Duplicate trigger detection
* Dependency cycle detection
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .cron_parser import CronParser


class TriggerValidationError(Exception):
    """Raised when trigger configuration fails validation."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class TriggerValidator:
    """Validates trigger definitions before registration.

    Usage::

        validator = TriggerValidator()
        validator.validate_cron("*/5 * * * * *")  # ok
        validator.validate_interval(seconds=30)    # ok
        validator.validate_interval(seconds=-1)    # raises
    """

    # Valid markets for calendar triggers
    VALID_MARKETS = {"CN", "US", "HK", "JP", "UK", "EU", "CRYPTO", "CUSTOM"}

    # Valid session identifiers
    VALID_SESSIONS = {
        "PRE_MARKET",
        "MORNING",
        "AFTERNOON",
        "AFTER_HOURS",
        "NIGHT",
        "CONTINUOUS",
        "FULL_DAY",
    }

    # Maximum reasonable interval values
    MAX_INTERVAL_SECONDS = 365 * 24 * 3600  # 1 year
    MAX_INTERVAL_MINUTES = 365 * 24 * 60
    MAX_INTERVAL_HOURS = 365 * 24
    MAX_INTERVAL_MS = 365 * 24 * 3600 * 1000

    def __init__(self) -> None:
        self._parser = CronParser()

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    def validate_cron(self, expression: str) -> Tuple[bool, Optional[str]]:
        """Validate a cron expression. Returns (ok, error_message)."""
        if not expression or not expression.strip():
            return False, "Cron expression must not be empty"
        try:
            self._parser.parse(expression.strip())
            return True, None
        except Exception as e:
            return False, str(e)

    def require_valid_cron(self, expression: str, field: str = "expression") -> None:
        ok, err = self.validate_cron(expression)
        if not ok:
            raise TriggerValidationError(err or "Invalid cron expression", field=field)

    # ------------------------------------------------------------------
    # Interval
    # ------------------------------------------------------------------

    def validate_interval(
        self,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        milliseconds: int = 0,
    ) -> Tuple[bool, Optional[str]]:
        """Validate interval parameters. At least one must be positive."""
        total_ms = (
            milliseconds
            + seconds * 1000
            + minutes * 60 * 1000
            + hours * 3600 * 1000
        )
        if total_ms <= 0:
            return False, "At least one interval value must be positive"
        if seconds < 0 or minutes < 0 or hours < 0 or milliseconds < 0:
            return False, "Interval values must be non-negative"
        if seconds > self.MAX_INTERVAL_SECONDS:
            return False, f"Seconds exceeds maximum ({self.MAX_INTERVAL_SECONDS})"
        if minutes > self.MAX_INTERVAL_MINUTES:
            return False, f"Minutes exceeds maximum ({self.MAX_INTERVAL_MINUTES})"
        if hours > self.MAX_INTERVAL_HOURS:
            return False, f"Hours exceeds maximum ({self.MAX_INTERVAL_HOURS})"
        if milliseconds > self.MAX_INTERVAL_MS:
            return False, f"Milliseconds exceeds maximum ({self.MAX_INTERVAL_MS})"
        return True, None

    def require_valid_interval(
        self,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        milliseconds: int = 0,
    ) -> None:
        ok, err = self.validate_interval(seconds, minutes, hours, milliseconds)
        if not ok:
            raise TriggerValidationError(err or "Invalid interval", field="interval")

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def validate_calendar(self, market: str, session: str = "CONTINUOUS") -> Tuple[bool, Optional[str]]:
        if market.upper() not in self.VALID_MARKETS:
            return False, f"Unknown market '{market}'. Valid: {self.VALID_MARKETS}"
        if session.upper() not in self.VALID_SESSIONS:
            return False, f"Unknown session '{session}'. Valid: {self.VALID_SESSIONS}"
        return True, None

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def check_duplicate(
        self,
        existing_triggers: List[Dict[str, Any]],
        new_trigger: Dict[str, Any],
    ) -> Optional[str]:
        """Return duplicate trigger_id if found, else None."""
        new_expr = new_trigger.get("expression", "")
        new_type = new_trigger.get("trigger_type", "")
        new_target = new_trigger.get("target", "")
        for t in existing_triggers:
            if (
                t.get("expression") == new_expr
                and t.get("trigger_type") == new_type
                and t.get("target") == new_target
            ):
                return t.get("trigger_id")
        return None

    # ------------------------------------------------------------------
    # Dependency cycle detection (simple DFS)
    # ------------------------------------------------------------------

    def check_dependency_cycles(
        self,
        trigger_id: str,
        depends_on: List[str],
        all_deps: Dict[str, List[str]],
    ) -> Tuple[bool, Optional[List[str]]]:
        """Detect cycles in trigger dependency graph. Returns (has_cycle, cycle_path)."""
        visited: set = set()
        path: List[str] = []

        def dfs(node: str) -> bool:
            if node in path:
                return True
            if node in visited:
                return False
            visited.add(node)
            path.append(node)
            for dep in all_deps.get(node, []):
                if dfs(dep):
                    return True
            path.pop()
            return False

        # Temporarily add the proposed dependency
        temp_deps = {k: list(v) for k, v in all_deps.items()}
        temp_deps[trigger_id] = list(depends_on)

        if dfs(trigger_id):
            return True, list(path)
        return False, None
