"""
CommandPolicy — which commands are allowed per severity, and whether an
approval is required.

High and critical severity incidents gate every control command behind an
explicit, auditable approval chain (spec section 4).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..incident_severity import IncidentSeverity
from .command import CommandType

# Commands available on any incident regardless of severity.
_BASE_COMMANDS = frozenset(
    {
        CommandType.ACKNOWLEDGE,
        CommandType.START_MITIGATION,
        CommandType.RESOLVE,
        CommandType.CLOSE,
        CommandType.REOPEN,
    }
)

# Operational commands that are only opened up from MEDIUM upwards.
_OPERATIONAL_COMMANDS = frozenset(
    {
        CommandType.EXECUTE_MITIGATION,
        CommandType.ESCALATE,
    }
)


@dataclass(frozen=True)
class CommandPolicy:
    allowed_commands: frozenset[CommandType]
    approval_required: bool = False


DEFAULT_COMMAND_POLICIES = {
    IncidentSeverity.INFO: CommandPolicy(
        allowed_commands=_BASE_COMMANDS,
        approval_required=False,
    ),
    IncidentSeverity.LOW: CommandPolicy(
        allowed_commands=_BASE_COMMANDS,
        approval_required=False,
    ),
    IncidentSeverity.MEDIUM: CommandPolicy(
        allowed_commands=_BASE_COMMANDS | _OPERATIONAL_COMMANDS,
        approval_required=False,
    ),
    IncidentSeverity.HIGH: CommandPolicy(
        allowed_commands=_BASE_COMMANDS | _OPERATIONAL_COMMANDS,
        approval_required=True,
    ),
    IncidentSeverity.CRITICAL: CommandPolicy(
        allowed_commands=_BASE_COMMANDS | _OPERATIONAL_COMMANDS,
        approval_required=True,
    ),
    IncidentSeverity.FATAL: CommandPolicy(
        allowed_commands=_BASE_COMMANDS | _OPERATIONAL_COMMANDS,
        approval_required=True,
    ),
}
