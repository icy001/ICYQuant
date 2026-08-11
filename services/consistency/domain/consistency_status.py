"""
Consistency status enums for cross-domain monitoring.

Defines the state machine for consistency checks:
    HEALTHY -> DEGRADED -> INCONSISTENT -> REPAIRING -> HEALTHY
                                  |
                                  v
                            ESCALATED
"""

from __future__ import annotations

from enum import Enum


class ConsistencyDomainStatus(str, Enum):
    """Per-domain consistency check status."""

    CONSISTENT = "CONSISTENT"
    """All metrics match — domain state == expected state."""

    DEGRADED = "DEGRADED"
    """Temporary async lag detected — within grace period."""

    INCONSISTENT = "INCONSISTENT"
    """Persistent mismatch — reconciliation required."""

    REPAIRING = "REPAIRING"
    """Reconciliation in progress — state being repaired."""

    HEALTHY = "HEALTHY"
    """Alias for CONSISTENT — used for state-machine transitions."""

    ESCALATED = "ESCALATED"
    """Automatic repair failed — human intervention required."""


class ReconciliationTriggerPriority(int, Enum):
    """Priority levels for reconciliation triggers."""

    P0 = 0  # ACCOUNTING_IMBALANCE — critical
    P1 = 1  # LEDGER_AMOUNT_MISMATCH / POSITION_OVERSTATE — severe
    P2 = 2  # MISSING_LEDGER_ENTRY / POSITION_MISMATCH — auto-repairable
    P3 = 3  # EVENT_LAG — wait for convergence
