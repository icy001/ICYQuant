"""Cron Expression — immutable representation of a parsed cron schedule.

Supports both 5-field (standard) and 6-field (seconds) cron expressions.
Each field is stored as a parsed :class:`CronField`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CronField:
    """A single field in a cron expression.

    Values is the expanded set of matching integers for the field.
    For wildcards this is generated; for lists/ranges it is resolved.
    """

    name: str  # second, minute, hour, day, month, weekday
    raw: str  # original expression fragment
    values: Tuple[int, ...]  # expanded integer values
    min_val: int
    max_val: int

    def matches(self, value: int) -> bool:
        return value in self.values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "raw": self.raw,
            "values": list(self.values),
            "min": self.min_val,
            "max": self.max_val,
        }


@dataclass(frozen=True)
class CronExpression:
    """Immutable parsed cron expression.

    Supports 6-field (second-aware) and 5-field (minute-based) formats.

    Fields (6-field): second minute hour day month weekday
    Fields (5-field):          minute hour day month weekday
    """

    expression: str
    fields: Tuple[CronField, ...]  # ordered: second, minute, hour, day, month, weekday
    is_six_field: bool = True
    timezone: str = "UTC"

    @property
    def second(self) -> CronField:
        if self.is_six_field:
            return self.fields[0]
        return CronField("second", "*", tuple(range(0, 60)), 0, 59)

    @property
    def minute(self) -> CronField:
        return self.fields[1] if self.is_six_field else self.fields[0]

    @property
    def hour(self) -> CronField:
        return self.fields[2] if self.is_six_field else self.fields[1]

    @property
    def day(self) -> CronField:
        return self.fields[3] if self.is_six_field else self.fields[2]

    @property
    def month(self) -> CronField:
        return self.fields[4] if self.is_six_field else self.fields[3]

    @property
    def weekday(self) -> CronField:
        return self.fields[5] if self.is_six_field else self.fields[4]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expression": self.expression,
            "is_six_field": self.is_six_field,
            "timezone": self.timezone,
            "fields": [f.to_dict() for f in self.fields],
        }

    def __repr__(self) -> str:
        return f"CronExpression('{self.expression}')"
