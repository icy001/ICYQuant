"""Cron Parser — parses and validates cron expressions.

Supports:
* Standard 5-field Linux cron (minute hour day month weekday)
* Extended 6-field with seconds (Quartz-compatible)
* Wildcards (*), ranges (1-5), lists (1,3,5), steps (*/5, 1-10/2)
* Named aliases (@yearly, @monthly, @weekly, @daily, @hourly)
* Month/weekday names (JAN-DEC, MON-SUN)

The parser produces an immutable :class:`CronExpression` with expanded
integer value sets for each field.
"""

from __future__ import annotations

import calendar as cal_mod
import re
from typing import List, Tuple

from .cron_expression import CronExpression, CronField

# Month name aliases (3-letter, uppercase)
_MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Weekday name aliases (3-letter, uppercase)
_WEEKDAY_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3,
    "THU": 4, "FRI": 5, "SAT": 6,
}

# Named preset expressions
_PRESETS: dict = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# Field definitions: (name, min, max, aliases)
_FIELD_DEFS = [
    ("second", 0, 59, {}),
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day", 1, 31, {}),
    ("month", 1, 12, _MONTH_NAMES),
    ("weekday", 0, 6, _WEEKDAY_NAMES),
]


class CronParseError(Exception):
    """Raised when a cron expression cannot be parsed."""


class CronParser:
    """Parses cron expressions into :class:`CronExpression` instances.

    Usage::

        parser = CronParser()
        expr = parser.parse("*/5 * * * * *")         # every 5 seconds
        expr = parser.parse("0 30 9 * * MON-FRI")    # 9:30 AM weekdays
        expr = parser.parse("@daily")                 # midnight every day
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, expression: str) -> CronExpression:
        """Parse a cron expression string into a CronExpression.

        Raises CronParseError if the expression is invalid.
        """
        expr = expression.strip()

        # Resolve named presets
        if expr.startswith("@"):
            expr = _PRESETS.get(expr.lower())
            if expr is None:
                raise CronParseError(f"Unknown preset: {expression}")

        # Determine 5-field vs 6-field
        parts = expr.split()
        if len(parts) == 5:
            is_six_field = False
            # Prepend a "0" second field for consistency
            parts = ["0"] + parts
        elif len(parts) == 6:
            is_six_field = True
        else:
            raise CronParseError(
                f"Expected 5 or 6 fields, got {len(parts)}: {expression}"
            )

        fields: List[CronField] = []
        for (name, min_v, max_v, aliases), raw in zip(_FIELD_DEFS, parts):
            resolved = self._resolve_aliases(raw.upper(), aliases)
            values = self._expand(resolved, min_v, max_v)
            fields.append(
                CronField(
                    name=name,
                    raw=raw,
                    values=tuple(sorted(values)),
                    min_val=min_v,
                    max_val=max_v,
                )
            )

        return CronExpression(
            expression=expression,
            fields=tuple(fields),
            is_six_field=is_six_field,
        )

    def get_next_fire_time(
        self,
        expression: CronExpression,
        from_time: "datetime | None" = None,
    ) -> "datetime | None":
        """Calculate the next fire time after *from_time* (or now).

        Returns None if the expression will never fire again.
        """
        import datetime as dt_mod

        now = from_time or dt_mod.datetime.now(dt_mod.timezone.utc)
        # Start at the next second
        current = now.replace(microsecond=0) + dt_mod.timedelta(seconds=1)

        # Search up to 4 years ahead
        end = current + dt_mod.timedelta(days=365 * 4)
        while current <= end:
            if self._matches(expression, current):
                return current
            current += dt_mod.timedelta(seconds=1)
        return None

    def get_next_n_fire_times(
        self,
        expression: CronExpression,
        n: int = 10,
        from_time: "datetime | None" = None,
    ) -> "list[datetime]":
        """Return the next *n* fire times."""
        import datetime as dt_mod

        results = []
        current = from_time or dt_mod.datetime.now(dt_mod.timezone.utc)
        for _ in range(n):
            nxt = self.get_next_fire_time(expression, current)
            if nxt is None:
                break
            results.append(nxt)
            current = nxt
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_aliases(self, raw: str, aliases: dict) -> str:
        """Replace month/weekday names with their numeric equivalents."""
        for name, num in aliases.items():
            raw = raw.replace(name, str(num))
        return raw

    def _expand(self, raw: str, min_val: int, max_val: int) -> List[int]:
        """Expand a cron field fragment into a set of integer values."""
        # Wildcard
        if raw == "*":
            return list(range(min_val, max_val + 1))

        # Wildcard with step: */5
        step_match = re.match(r"^\*/(\d+)$", raw)
        if step_match:
            step = int(step_match.group(1))
            if step <= 0:
                raise CronParseError(f"Step must be positive: {raw}")
            return list(range(min_val, max_val + 1, step))

        values: set = set()
        for part in raw.split(","):
            part = part.strip()

            # Range with step: 1-10/2
            range_step_match = re.match(r"^(\d+)-(\d+)/(\d+)$", part)
            if range_step_match:
                lo, hi, step = map(int, range_step_match.groups())
                if step <= 0:
                    raise CronParseError(f"Step must be positive: {part}")
                values.update(range(lo, hi + 1, step))
                continue

            # Simple range: 1-5
            range_match = re.match(r"^(\d+)-(\d+)$", part)
            if range_match:
                lo, hi = map(int, range_match.groups())
                values.update(range(lo, hi + 1))
                continue

            # Single value
            if part.isdigit():
                val = int(part)
                values.add(val)
                continue

            raise CronParseError(f"Cannot parse cron field fragment: {raw!r} (part={part!r})")

        # Validate bounds
        for v in values:
            if v < min_val or v > max_val:
                raise CronParseError(
                    f"Value {v} out of range [{min_val}, {max_val}] in field: {raw}"
                )

        return sorted(values)

    @staticmethod
    def _matches(expression: CronExpression, dt: "datetime") -> bool:
        return (
            expression.second.matches(dt.second)
            and expression.minute.matches(dt.minute)
            and expression.hour.matches(dt.hour)
            and expression.day.matches(dt.day)
            and expression.month.matches(dt.month)
            and expression.weekday.matches(dt.weekday())
        )
