"""
Trading Flow — orchestrates the domain-level trading lifecycle.

Commit 21 Part 1.1: bridges the ControlFlow (governance state machine) with
the TradingContext (actual trade parameters) and TradingResult (final outcome).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_flow import ControlFlow
from .control_state import ControlFlowState
from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus
from .trading_context import TradingContext
from .trading_result import TradingResult, TradingOutcome
from .trading_transition import TradingTransition, TradingTransitionType


@dataclass
class TradingFlow:
    """Domain-level trading lifecycle orchestrator.

    Wraps a ControlFlow with domain-specific trading data.
    """

    # ── Identity ───────────────────────────────────────────────
    flow_id: str = field(default_factory=lambda: f"FLOW-{uuid.uuid4().hex[:12].upper()}")

    # ── Context ────────────────────────────────────────────────
    control_context: TradingControlContext = field(default_factory=TradingControlContext)
    trading_context: TradingContext = field(default_factory=TradingContext)

    # ── Control Flow ───────────────────────────────────────────
    control_flow: Optional[ControlFlow] = None

    # ── Trading-specific transitions ───────────────────────────
    _trading_transitions: List[TradingTransition] = field(default_factory=list)

    # ── Timing ─────────────────────────────────────────────────
    started_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.control_flow is None:
            self.control_flow = ControlFlow(
                flow_id=self.flow_id,
                context=self.control_context,
            )

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> TradingTransition:
        """Begin the trading flow."""
        self.started_at = time.time()
        tt = TradingTransition(
            transition_type=TradingTransitionType.DECISION_CREATED,
            flow_id=self.flow_id,
            decision_id=self.control_context.decision_id or "",
            quantity=self.trading_context.quantity,
            price=self.trading_context.price,
            notional=self.trading_context.notional,
        )
        self._trading_transitions.append(tt)
        return tt

    def record_order_created(self, order_id: str) -> TradingTransition:
        """Record that an order was created."""
        tt = TradingTransition(
            transition_type=TradingTransitionType.ORDER_CREATED,
            flow_id=self.flow_id,
            order_id=order_id,
            decision_id=self.control_context.decision_id or "",
            quantity=self.trading_context.quantity,
            price=self.trading_context.price,
            notional=self.trading_context.notional,
        )
        self._trading_transitions.append(tt)
        return tt

    def record_order_submitted(self, order_id: str) -> TradingTransition:
        """Record that an order was submitted."""
        tt = TradingTransition(
            transition_type=TradingTransitionType.ORDER_SUBMITTED,
            flow_id=self.flow_id,
            order_id=order_id,
            decision_id=self.control_context.decision_id or "",
            quantity=self.trading_context.quantity,
            price=self.trading_context.price,
            notional=self.trading_context.notional,
        )
        self._trading_transitions.append(tt)
        return tt

    def finalize(self, final_state: ControlFlowState, reason: str = "") -> TradingResult:
        """Produce the final trading result."""
        gate_results = {}
        if self.control_flow:
            gate_results = self.control_flow._gate_results

        result = TradingResult.from_flow(
            flow_id=self.flow_id,
            decision_id=self.control_context.decision_id or "",
            final_state=final_state,
            gate_results=gate_results,
            transition_count=(len(self.control_flow._transitions)
                              if self.control_flow else 0),
            started_at=self.started_at,
            reason=reason,
        )
        return result

    @property
    def trading_transitions(self) -> List[TradingTransition]:
        return list(self._trading_transitions)

    @property
    def current_state(self) -> ControlFlowState:
        if self.control_flow:
            return self.control_flow.current_state
        return ControlFlowState.PROPOSED

    def summary(self) -> Dict[str, Any]:
        flow_summary = self.control_flow.summary() if self.control_flow else {}
        return {
            "flow_id": self.flow_id,
            "decision_id": self.control_context.decision_id,
            "symbol": self.trading_context.symbol,
            "side": self.trading_context.side,
            "quantity": self.trading_context.quantity,
            "notional": self.trading_context.notional,
            "current_state": self.current_state.name,
            "started_at": self.started_at,
            "trading_transitions": [t.to_dict() for t in self._trading_transitions],
            "control_flow": flow_summary,
        }
