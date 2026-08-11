"""OMS results package — command results and errors."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "CommandResult": ".command_result",
        "CommandError": ".command_errors",
        "CommandValidationError": ".command_errors",
        "CommandExecutionError": ".command_errors",
        "DuplicateCommandError": ".command_errors",
        "ConcurrencyConflictError": ".command_errors",
        "ExecutionIdConflictError": ".command_errors",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "CommandResult",
    "CommandError",
    "CommandValidationError",
    "CommandExecutionError",
    "DuplicateCommandError",
    "ConcurrencyConflictError",
    "ExecutionIdConflictError",
]
