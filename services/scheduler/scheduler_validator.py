"""Scheduler Validator — validates schedule definitions for correctness.

The :class:`SchedulerValidator` performs comprehensive validation on
schedule definitions before they are registered or executed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from .models.schedule import ScheduleDefinition, ScheduleType

logger = logging.getLogger(__name__)

# ── validation errors ─────────────────────────────────────────────────────


class ValidationError:
    """A single validation error."""

    def __init__(self, field: str, message: str, code: str = "invalid") -> None:
        self.field = field
        self.message = message
        self.code = code

    def to_dict(self) -> Dict[str, str]:
        return {"field": self.field, "message": self.message, "code": self.code}

    def __repr__(self) -> str:
        return f"ValidationError({self.field}: {self.message})"


# ── individual checks ─────────────────────────────────────────────────────


def _check_required_fields(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Check that all required fields are present."""
    errors: List[ValidationError] = []
    if not schedule.schedule_id:
        errors.append(ValidationError("schedule_id", "is required", "missing"))
    if not schedule.name:
        errors.append(ValidationError("name", "is required", "missing"))
    if not schedule.trigger_expression:
        errors.append(ValidationError("trigger_expression", "is required", "missing"))
    if not schedule.target:
        errors.append(ValidationError("target", "is required", "missing"))
    return errors


def _check_cron_expression(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Validate cron expression format."""
    errors: List[ValidationError] = []
    if schedule.schedule_type != ScheduleType.CRON:
        return errors

    expr = schedule.trigger_expression.strip()
    if not expr:
        return errors

    parts = expr.split()
    if len(parts) < 5:
        errors.append(ValidationError(
            "trigger_expression",
            f"cron expression must have at least 5 fields, got {len(parts)}: '{expr}'",
            "invalid_cron",
        ))
        return errors

    # Basic field count check (5 or 6 for seconds)
    if len(parts) not in (5, 6):
        errors.append(ValidationError(
            "trigger_expression",
            f"cron expression must have 5 or 6 fields, got {len(parts)}",
            "invalid_cron",
        ))

    # Validate individual fields (simplified)
    for i, field in enumerate(parts):
        valid_chars = set("*,-/0123456789?LW#")
        for ch in field:
            if ch not in valid_chars:
                errors.append(ValidationError(
                    "trigger_expression",
                    f"invalid character '{ch}' in cron field {i}: '{field}'",
                    "invalid_cron_char",
                ))
                break

    return errors


def _check_interval_expression(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Validate ISO 8601 interval expression."""
    errors: List[ValidationError] = []
    if schedule.schedule_type != ScheduleType.INTERVAL:
        return errors

    expr = schedule.trigger_expression.strip()
    if not expr.startswith("P"):
        errors.append(ValidationError(
            "trigger_expression",
            f"ISO 8601 interval must start with 'P': '{expr}'",
            "invalid_interval",
        ))
        return errors

    # Check for at least one time unit designator
    has_time_unit = any(c in expr for c in "YMWDTHMS")
    if not has_time_unit:
        errors.append(ValidationError(
            "trigger_expression",
            f"no time unit found in interval: '{expr}'",
            "invalid_interval",
        ))

    return errors


def _check_duplicate_schedule(
    schedule: ScheduleDefinition, existing_ids: Optional[Set[str]] = None,
) -> List[ValidationError]:
    """Check for duplicate schedule IDs (requires external context)."""
    return []


def _check_overlap_policy(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Validate overlap policy."""
    errors: List[ValidationError] = []
    valid_policies = {"skip", "allow", "queue"}
    if schedule.config.overlapping_policy not in valid_policies:
        errors.append(ValidationError(
            "config.overlapping_policy",
            f"must be one of {valid_policies}, got '{schedule.config.overlapping_policy}'",
            "invalid_policy",
        ))
    return errors


def _check_misfire_policy(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Validate misfire policy."""
    errors: List[ValidationError] = []
    valid_policies = {"ignore", "fire_once", "fire_all"}
    if schedule.config.misfire_policy not in valid_policies:
        errors.append(ValidationError(
            "config.misfire_policy",
            f"must be one of {valid_policies}, got '{schedule.config.misfire_policy}'",
            "invalid_policy",
        ))
    return errors


def _check_numeric_config(schedule: ScheduleDefinition) -> List[ValidationError]:
    """Validate numeric config fields."""
    errors: List[ValidationError] = []
    if schedule.config.max_concurrent < 1:
        errors.append(ValidationError(
            "config.max_concurrent",
            f"must be >= 1, got {schedule.config.max_concurrent}",
            "invalid_range",
        ))
    if schedule.config.max_concurrent > 1000:
        errors.append(ValidationError(
            "config.max_concurrent",
            f"must be <= 1000, got {schedule.config.max_concurrent}",
            "invalid_range",
        ))
    if schedule.config.retry_max < 0:
        errors.append(ValidationError(
            "config.retry_max",
            f"must be >= 0, got {schedule.config.retry_max}",
            "invalid_range",
        ))
    if schedule.config.retry_max > 100:
        errors.append(ValidationError(
            "config.retry_max",
            f"must be <= 100, got {schedule.config.retry_max}",
            "invalid_range",
        ))
    if schedule.config.retry_delay_seconds < 0:
        errors.append(ValidationError(
            "config.retry_delay_seconds",
            f"must be >= 0, got {schedule.config.retry_delay_seconds}",
            "invalid_range",
        ))
    if schedule.config.priority < 0 or schedule.config.priority > 255:
        errors.append(ValidationError(
            "config.priority",
            f"must be 0-255, got {schedule.config.priority}",
            "invalid_range",
        ))
    return errors


# ── main validation ───────────────────────────────────────────────────────


def validate_schedule(
    schedule: ScheduleDefinition,
    existing_ids: Optional[Set[str]] = None,
) -> List[ValidationError]:
    """Validate a schedule definition.

    Performs all validation checks and returns a list of errors.
    An empty list means the schedule is valid.

    Checks performed:
    * Required fields present
    * Cron expression validity (for cron schedules)
    * Interval expression validity (for interval schedules)
    * Overlap policy
    * Misfire policy
    * Numeric config ranges

    Usage::

        errors = validate_schedule(my_schedule)
        if errors:
            for e in errors:
                print(f"{e.field}: {e.message}")
    """
    errors: List[ValidationError] = []

    # Basic checks
    errors.extend(_check_required_fields(schedule))
    errors.extend(_check_numeric_config(schedule))

    # Schedule-type-specific checks
    if schedule.schedule_type == ScheduleType.CRON:
        errors.extend(_check_cron_expression(schedule))
    elif schedule.schedule_type == ScheduleType.INTERVAL:
        errors.extend(_check_interval_expression(schedule))

    # Policy checks
    errors.extend(_check_overlap_policy(schedule))
    errors.extend(_check_misfire_policy(schedule))

    return errors


def validate_schedule_config(data: Dict[str, Any]) -> List[ValidationError]:
    """Validate a raw schedule configuration dict before parsing.

    Useful for pre-validation of user input from API endpoints.
    """
    errors: List[ValidationError] = []

    required = ["schedule_id", "name", "trigger_expression", "target"]
    for field in required:
        if not data.get(field):
            errors.append(ValidationError(field, "is required", "missing"))

    schedule_type = data.get("schedule_type", "cron")
    valid_types = {t.value for t in ScheduleType}
    if schedule_type not in valid_types:
        errors.append(ValidationError(
            "schedule_type",
            f"must be one of {valid_types}, got '{schedule_type}'",
            "invalid_type",
        ))

    return errors
