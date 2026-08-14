"""Execution adapters (Commit 38 Part 1.3).

Concrete implementations of the :class:`ExecutionAdapter` port.  Each adapter
wraps one external venue's protocol so that broker-specific logic never
pollutes the Execution domain.
"""

from services.execution.adapters.simulator import (
    SimulatorExecutionAdapter,
)

__all__ = [
    "SimulatorExecutionAdapter",
]
