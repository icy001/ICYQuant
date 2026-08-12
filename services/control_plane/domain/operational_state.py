"""
OperationalState — a unified expression of "what the system is doing right now".

Unlike SystemState (where the system *is*) and TradingState (whether trading is
*allowed*), OperationalState describes the current mode of operation:

    NORMAL        everything nominal
    DEGRADED      running below nominal quality, no recovery in progress
    RECOVERY      an automatic recovery is being executed
    HALT          trading stopped (manual halt) while the system keeps running
    MAINTENANCE   scheduled maintenance window
    EMERGENCY     emergency halt — risk critical path broken
"""

from __future__ import annotations

from enum import Enum


class OperationalState(str, Enum):
    """Current operational mode of the system."""

    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    RECOVERY = "RECOVERY"
    HALT = "HALT"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"
