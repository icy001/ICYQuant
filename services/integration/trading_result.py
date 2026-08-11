"""
Trading Result — final outcome of a trading flow through the institutional pipeline.

Commit 21 Part 1.1: captures whether the flow completed normally or was stopped,
with full correlation data for audit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .control_state import ControlFlowState
from .control_result import ControlResult, GateStatus


class TradingOutcome(Enum):
    """Final trading outcome."""
    EXECUTED = auto()        # Order fully executed
    REJECTED = auto()        # Gate rejected
    BLOCKED = auto()         # Gate blocked (fail-closed)
    FROZEN = auto()          # Governance freeze
    CANCELLED = auto()       # Manual cancellation
    EXPIRED = auto()         # Expired before execution
    FAILED = auto()          # Technical failure
    PARTIAL = auto()         # Partially executed


@dataclass
class TradingResult:
    """Final result of a trading flow through the institutional pipeline."""

    # ── Identity ───────────────────────────────────────────────
    flow_id: str = ""
    decision_id: str = ""

    # ── Outcome ────────────────────────────────────────────────
    outcome: TradingOutcome = TradingOutcome.REJECTED
    final_state: ControlFlowState = ControlFlowState.PROPOSED
    success: bool = False

    # ── Order ──────────────────────────────────────────────────
    order_id: Optional[str] = None
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None

    # ── Gate Results ───────────────────────────────────────────
    gate_results: Dict[str, ControlResult] = field(default_factory=dict)

    # ── Transitions ────────────────────────────────────────────
    transition_count: int = 0

    # ── Timing ─────────────────────────────────────────────────
    started_at: float = 0.0
    completed_at: float = field(default_factory=time.time)
    latency_ms: float = 0.0

    # ── Reasons ────────────────────────────────────────────────
    reason: str = ""
    errors: List[str] = field(default_factory=list)

    # ── Metadata ───────────────────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_flow(
        cls,
        flow_id: str,
        decision_id: str,
        final_state: ControlFlowState,
        gate_results: Dict[str, ControlResult],
        transition_count: int,
        started_at: float,
        reason: str = "",
    ) -> "TradingResult":
        """Build a result from a completed ControlFlow."""
        outcome_map = {
            ControlFlowState.EXECUTED: TradingOutcome.EXECUTED,
            ControlFlowState.REJECTED: TradingOutcome.REJECTED,
            ControlFlowState.BLOCKED: TradingOutcome.BLOCKED,
            ControlFlowState.FROZEN: TradingOutcome.FROZEN,
            ControlFlowState.CANCELLED: TradingOutcome.CANCELLED,
            ControlFlowState.EXPIRED: TradingOutcome.EXPIRED,
            ControlFlowState.FAILED: TradingOutcome.FAILED,
        }
        outcome = outcome_map.get(final_state, TradingOutcome.FAILED)
        success = final_state == ControlFlowState.EXECUTED

        return cls(
            flow_id=flow_id,
            decision_id=decision_id,
            outcome=outcome,
            final_state=final_state,
            success=success,
            gate_results=gate_results,
            transition_count=transition_count,
            started_at=started_at,
            reason=reason,
            latency_ms=(time.time() - started_at) * 1000 if started_at else 0.0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "outcome": self.outcome.name,
            "final_state": self.final_state.name,
            "success": self.success,
            "order_id": self.order_id,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "gate_results": {k: v.to_dict() for k, v in self.gate_results.items()},
            "transition_count": self.transition_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "latency_ms": self.latency_ms,
            "reason": self.reason,
            "errors": self.errors,
            "metadata": self.metadata,
        }
