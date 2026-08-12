"""
GateReason — canonical reasons for a gate DENY (and the ALLOW reason).

Production environments must never emit ``DENY / reason="something wrong"``.
Every denial maps to one of these codes so the Control Plane, audit and
alerting can react deterministically.

Standard denial reasons (spec section 6):

    SYSTEM_NOT_READY        system not in READY state
    TRADING_HALTED          trading state is TRADING_HALTED
    RISK_ENGINE_UNHEALTHY   risk engine not HEALTHY
    EXECUTION_ENGINE_UNHEALTHY   execution engine not HEALTHY
    EVENT_BUS_UNHEALTHY     event bus not HEALTHY
    POSITION_STATE_UNTRUSTED    position state is UNTRUSTED
    LEDGER_STATE_UNTRUSTED      ledger state is UNTRUSTED
    MARKET_DATA_STALE       market data is STALE / EXPIRED
    RECOVERY_IN_PROGRESS    an active recovery is blocking new orders
    MANUAL_HALT             manual trading halt
    EMERGENCY_HALT          emergency halt (kill switch / emergency state)
    MAINTENANCE_MODE        scheduled maintenance window
"""

from __future__ import annotations

from enum import Enum


class GateReason(str, Enum):
    """Canonical reasons for a gate decision."""

    SYSTEM_NOT_READY = "SYSTEM_NOT_READY"
    TRADING_HALTED = "TRADING_HALTED"
    RISK_ENGINE_UNHEALTHY = "RISK_ENGINE_UNHEALTHY"
    EXECUTION_ENGINE_UNHEALTHY = "EXECUTION_ENGINE_UNHEALTHY"
    EVENT_BUS_UNHEALTHY = "EVENT_BUS_UNHEALTHY"
    POSITION_STATE_UNTRUSTED = "POSITION_STATE_UNTRUSTED"
    LEDGER_STATE_UNTRUSTED = "LEDGER_STATE_UNTRUSTED"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    MANUAL_HALT = "MANUAL_HALT"
    EMERGENCY_HALT = "EMERGENCY_HALT"
    MAINTENANCE_MODE = "MAINTENANCE_MODE"
    RISK_NOT_APPROVED = "RISK_NOT_APPROVED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    SYSTEM_HEALTHY = "SYSTEM_HEALTHY"

    @property
    def is_allow(self) -> bool:
        return self is GateReason.SYSTEM_HEALTHY
