"""
Governance Gate — validates governance constraints before trade proceeds.

Commit 21 Part 1.1: checks Policy, Governance State, Strategy Restrictions,
Emergency State, Market Restrictions, and Control Actions.

KEY INVARIANT: if GovernanceState == FROZEN → BLOCK (not REJECT).
FROZEN means the system is frozen, not that the trade is bad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from .control_gate import ControlGate
from .control_context import TradingControlContext
from .control_result import ControlResult


class GovernanceState(Enum):
    """Governance state types for gate configuration."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    RESTRICTED = "RESTRICTED"
    DEGRADED = "DEGRADED"
    FROZEN = "FROZEN"
    EMERGENCY = "EMERGENCY"
    RECOVERY = "RECOVERY"


@dataclass
class GovernanceGate(ControlGate):
    """Governance Gate — validates governance state and policies.

    Checks:
      - Governance State: NORMAL/WATCH/FROZEN/EMERGENCY
      - Policy Compliance: active policies
      - Strategy Restrictions: blocked strategies
      - Emergency State: emergency mode
      - Market Restrictions: trading halts, circuit breakers
    """

    name: str = "GovernanceGate"
    governance_state: str = "NORMAL"
    emergency_mode: bool = False
    frozen: bool = False
    blocked_strategies: list = field(default_factory=list)
    trading_halted: bool = False
    policy_violations: list = field(default_factory=list)

    def check(self, context: TradingControlContext) -> ControlResult:
        """Evaluate governance constraints."""

        # ── Emergency Mode ──────────────────────────────────────
        if self.emergency_mode:
            # In emergency, only risk-reducing actions allowed
            if context.decision_type not in ("CAPITAL_DEALLOCATION", "EMERGENCY_ACTION",
                                              "ORDER_CANCEL", "RISK_LIMIT_CHANGE"):
                return self.block_result(
                    context,
                    code="GOVERNANCE_EMERGENCY",
                    reason="Emergency mode: only risk-reducing actions allowed",
                )

        # ── Frozen ──────────────────────────────────────────────
        if self.frozen:
            return ControlResult.make_freeze(
                    flow_id=context.flow_id,
                    code="GOVERNANCE_FROZEN",
                    reason="Portfolio governance state is FROZEN — new orders blocked",
            )

        # ── Trading Halted ──────────────────────────────────────
        if self.trading_halted:
            return self.block_result(
                context,
                code="GOVERNANCE_TRADING_HALTED",
                reason="Trading is halted — market circuit breaker or restriction",
            )

        # ── Strategy Blocked ────────────────────────────────────
        if context.strategy_id and context.strategy_id in self.blocked_strategies:
            return self.reject_result(
                context,
                code="GOVERNANCE_STRATEGY_BLOCKED",
                reason=f"Strategy {context.strategy_id} is blocked by governance",
            )

        # ── Policy Violations ───────────────────────────────────
        if self.policy_violations:
            return self.reject_result(
                context,
                code="GOVERNANCE_POLICY_VIOLATION",
                reason=f"Policy violations: {', '.join(self.policy_violations)}",
            )

        # ── Governance State Check ──────────────────────────────
        if context.governance_context:
            gov = context.governance_context
            state = gov.get("governance_state", gov.get("state", "NORMAL"))

            if state in ("FROZEN",):
                return ControlResult.make_freeze(
                        flow_id=context.flow_id,
                        code="GOVERNANCE_FROZEN",
                        reason="Governance state is FROZEN",
                )
            elif state in ("EMERGENCY",):
                return self.block_result(
                    context,
                    code="GOVERNANCE_EMERGENCY",
                    reason="Governance state is EMERGENCY",
                )
            elif state in ("DEGRADED",):
                # Degraded — allow but warn
                pass
            elif state in ("UNKNOWN",):
                return self.fail_closed(context, "Governance state UNKNOWN")

        return self.pass_result(context, reason="Governance checks passed")



