"""
ExecutionState — the state model of an execution channel under Institutional
Control (Commit 26 Part 1.4, spec section 3).

Execution Control sits below Order Admission and above Venue Control: it
decides whether an execution channel may submit new orders, cancel open
orders, reduce positions or flatten in an emergency — independently.

    ACTIVE      normal execution
    DEGRADED    execution capability reduced
    PAUSED      new execution paused
    DRAINING    stop new entries, work existing orders
    DISABLED    execution fully forbidden
    FAILOVER    switching to a backup channel
"""

from __future__ import annotations

from enum import Enum


class ExecutionState(str, Enum):

    ACTIVE = "ACTIVE"

    DEGRADED = "DEGRADED"

    PAUSED = "PAUSED"

    DISABLED = "DISABLED"

    DRAINING = "DRAINING"

    FAILOVER = "FAILOVER"
