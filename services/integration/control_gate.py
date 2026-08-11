"""
Control Gate — abstract base for all control flow gates.

Commit 21 Part 1.1: every gate returns PASS / REJECT / BLOCK / FREEZE / EXPIRED / ERROR.
Fail-closed: UNKNOWN or indeterminate state → BLOCK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus


@dataclass
class ControlGate(ABC):
    """Abstract base for all control flow gates.

    Each gate evaluates one dimension of institutional control:
      - RiskGate:  exposure, leverage, drawdown, concentration
      - GovernanceGate: policy, state, restrictions
      - AuthorityGate: authority scope, limits, delegation
      - ApprovalGate: approval status, validity, scope
    """

    name: str = "ControlGate"
    enabled: bool = True

    # ── Core Interface ─────────────────────────────────────────

    @abstractmethod
    def check(self, context: TradingControlContext) -> ControlResult:
        """Evaluate whether this gate allows the flow to proceed.

        Returns:
            ControlResult with PASS / REJECT / BLOCK / FREEZE / EXPIRED / ERROR.
        """
        ...

    # ── Fail-Closed: Unknown → BLOCK ───────────────────────────

    def fail_closed(self, context: TradingControlContext, reason: str = "") -> ControlResult:
        """Return a BLOCK result — the fail-closed default.

        Used when a gate cannot determine state (timeout, error, missing data).
        NEVER defaults to PASS on indeterminate state.
        """
        return ControlResult.make_block(
            flow_id=context.flow_id,
            code=f"{self.name.upper()}_UNKNOWN",
            reason=reason or f"{self.name}: indeterminate state → BLOCK (fail-closed)",
        )

    # ── Convenience Methods ────────────────────────────────────

    def pass_result(self, context: TradingControlContext, reason: str = "",
                    **kwargs) -> ControlResult:
        return ControlResult.make_pass(
            flow_id=context.flow_id,
            reason=reason or f"{self.name}: PASS",
            **kwargs,
        )

    def reject_result(self, context: TradingControlContext, code: str = "",
                      reason: str = "", **kwargs) -> ControlResult:
        return ControlResult.make_reject(
            flow_id=context.flow_id,
            code=code or f"{self.name.upper()}_REJECTED",
            reason=reason or f"{self.name}: REJECT",
            **kwargs,
        )

    def block_result(self, context: TradingControlContext, code: str = "",
                     reason: str = "", **kwargs) -> ControlResult:
        return ControlResult.make_block(
            flow_id=context.flow_id,
            code=code or f"{self.name.upper()}_BLOCKED",
            reason=reason or f"{self.name}: BLOCK",
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"{self.name}(enabled={self.enabled})"
