"""
IncidentType — WHAT happened, not how severe it is.

The type describes the problem; severity is a separate dimension carried by
IncidentSeverity (spec section 4).
"""

from __future__ import annotations

from enum import Enum


class IncidentType(str, Enum):
    """Classification of the underlying problem."""

    HEALTH_FAILURE = "HEALTH_FAILURE"
    """A monitored component is unhealthy."""

    RISK_BREACH = "RISK_BREACH"
    """A risk limit or risk condition was breached."""

    POSITION_INTEGRITY_FAILURE = "POSITION_INTEGRITY_FAILURE"
    """Position state became untrusted."""

    LEDGER_INTEGRITY_FAILURE = "LEDGER_INTEGRITY_FAILURE"
    """Ledger state became untrusted."""

    EVENT_BUS_FAILURE = "EVENT_BUS_FAILURE"
    """Event bus connectivity or delivery failure."""

    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    """Execution engine / venue failure."""

    MARKET_DATA_FAILURE = "MARKET_DATA_FAILURE"
    """Market data missing, stale or corrupt."""

    RECONCILIATION_FAILURE = "RECONCILIATION_FAILURE"
    """Reconciliation mismatch or failure."""

    RECOVERY_FAILURE = "RECOVERY_FAILURE"
    """A recovery attempt failed."""

    POLICY_VIOLATION = "POLICY_VIOLATION"
    """A control policy was violated."""

    SYSTEM_FAILURE = "SYSTEM_FAILURE"
    """General system failure."""

    SECURITY_FAILURE = "SECURITY_FAILURE"
    """Security or access control failure."""
