"""
Flow Orchestrator — orchestrates the full institutional trading control flow.

Commit 21 Part 1.1: the central orchestrator that runs the pipeline:
Signal → Decision → RiskGate → GovernanceGate → AuthorityGate → ApprovalGate → OrderReady.

This is THE entry point — Strategy does NOT call Risk/Governance/Authority/Approval directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_flow import ControlFlow
from .control_state import ControlFlowState
from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus

from .trading_context import TradingContext
from .trading_flow import TradingFlow
from .trading_result import TradingResult, TradingOutcome

from .risk_gate import RiskGate, RiskGateConfig
from .governance_gate import GovernanceGate
from .authority_gate import AuthorityGate
from .approval_gate import ApprovalGate

from .signal_adapter import SignalAdapter, SignalInput
from .decision_adapter import DecisionAdapter
from .risk_adapter import RiskAdapter
from .governance_adapter import GovernanceAdapter
from .authority_adapter import AuthorityAdapter
from .approval_adapter import ApprovalAdapter
from .order_adapter import OrderAdapter, OrderIntent


@dataclass
class FlowOrchestrator:
    """Central orchestrator for institutional trading control flow.

    Orchestrates the full pipeline WITHOUT letting individual domains
    call each other directly.

    Pipeline:
        PROPOSED → VALIDATING → RISK_CHECKED → GOVERNANCE_CHECKED
        → AUTHORIZED → APPROVED → ORDER_READY
    """

    # ── Gates ──────────────────────────────────────────────────
    risk_gate: RiskGate = field(default_factory=RiskGate)
    governance_gate: GovernanceGate = field(default_factory=GovernanceGate)
    authority_gate: AuthorityGate = field(default_factory=AuthorityGate)
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)

    # ── Adapters ───────────────────────────────────────────────
    signal_adapter: SignalAdapter = field(default_factory=SignalAdapter)
    decision_adapter: DecisionAdapter = field(default_factory=DecisionAdapter)
    risk_adapter: RiskAdapter = field(default_factory=RiskAdapter)
    governance_adapter: GovernanceAdapter = field(default_factory=GovernanceAdapter)
    authority_adapter: AuthorityAdapter = field(default_factory=AuthorityAdapter)
    approval_adapter: ApprovalAdapter = field(default_factory=ApprovalAdapter)
    order_adapter: OrderAdapter = field(default_factory=OrderAdapter)

    # ── Audit ──────────────────────────────────────────────────
    _completed_flows: List[TradingFlow] = field(default_factory=list)

    # ── Fail-Closed: Invertible Gate Order ─────────────────────

    # The gate pipeline is hard-coded in order.
    # No gate can be skipped or reordered.
    _GATE_ORDER: tuple = ("risk", "governance", "authority", "approval")

    # ── Core Orchestration ─────────────────────────────────────

    def orchestrate(
        self,
        context: TradingControlContext,
        trading_ctx: Optional[TradingContext] = None,
    ) -> TradingResult:
        """Run the full institutional control flow.

        This is THE entry point. Returns a TradingResult with full audit trail.

        Args:
            context: The trading control context (from signal/decision).
            trading_ctx: Optional trading domain context.

        Returns:
            TradingResult with outcome, gate results, and transition history.
        """
        trading = trading_ctx or TradingContext()
        flow = TradingFlow(
            flow_id=context.flow_id,
            control_context=context,
            trading_context=trading,
        )
        flow.start()

        cf = flow.control_flow

        try:
            # ── Stage 1: VALIDATING ─────────────────────────────
            cf.advance_to_validating(actor="flow-orchestrator")

            # ── Stage 2: RISK_CHECKED ──────────────────────────
            result = self._evaluate_gate("risk", self.risk_gate, context, cf)
            if result is not None:
                return self._terminal(flow, result)

            cf.advance_to_risk_checked(
                actor="risk-gate",
                reason=result.reason if result else "Risk passed",
            )

            # ── Stage 3: GOVERNANCE_CHECKED ─────────────────────
            result = self._evaluate_gate("governance", self.governance_gate, context, cf)
            if result is not None:
                return self._terminal(flow, result)

            cf.advance_to_governance_checked(
                actor="governance-gate",
                reason=result.reason if result else "Governance passed",
            )

            # ── Stage 4: AUTHORIZED ─────────────────────────────
            result = self._evaluate_gate("authority", self.authority_gate, context, cf)
            if result is not None:
                return self._terminal(flow, result)

            cf.advance_to_authorized(
                actor="authority-gate",
                reason=result.reason if result else "Authority passed",
            )

            # ── Stage 5: APPROVED ───────────────────────────────
            result = self._evaluate_gate("approval", self.approval_gate, context, cf)
            if result is not None:
                return self._terminal(flow, result)

            cf.advance_to_approved(
                actor="approval-gate",
                reason=result.reason if result else "Approval passed",
            )

            # ── Stage 6: ORDER_READY ────────────────────────────
            cf.advance_to_order_ready(actor="flow-orchestrator", reason="All gates passed")

            # ── Stage 7-9: SUBMITTED → EXECUTING → EXECUTED ───
            cf.advance_to_submitted(actor="flow-orchestrator", reason="Order submitted")
            cf.advance_to_executing(actor="flow-orchestrator", reason="Order executing")
            cf.advance_to_executed(actor="flow-orchestrator", reason="Order executed")

            result = flow.finalize(ControlFlowState.EXECUTED, "All gates passed, order executed")
            self._completed_flows.append(flow)
            return result

        except Exception as e:
            cf.fail(reason=str(e), actor="flow-orchestrator")
            return flow.finalize(ControlFlowState.FAILED, str(e))

    def orchestrate_from_signal(
        self,
        signal: SignalInput,
        risk_data: Optional[Dict[str, Any]] = None,
        governance_data: Optional[Dict[str, Any]] = None,
        authority_data: Optional[Dict[str, Any]] = None,
        approval_data: Optional[Dict[str, Any]] = None,
    ) -> TradingResult:
        """Full end-to-end orchestration starting from a strategy signal.

        Args:
            signal: The strategy signal to process.
            risk_data: Pre-computed risk data (optional).
            governance_data: Pre-computed governance data (optional).
            authority_data: Pre-computed authority data (optional).
            approval_data: Pre-computed approval data (optional).

        Returns:
            TradingResult with outcome.
        """
        # Step 1: Adapt signal → control context
        context = self.signal_adapter.adapt(signal)

        # Step 2: Attach domain contexts if provided
        if risk_data:
            context.with_risk_context(risk_data)
        if governance_data:
            context.with_governance_context(governance_data)
        if authority_data:
            context.with_authority_context(authority_data)
        if approval_data:
            context.with_approval_context(approval_data)

        # Step 3: Build trading context
        trading = TradingContext(
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            price=signal.price,
            notional=signal.quantity * (signal.price or 0),
            strategy_name=signal.strategy_id,
            signal_score=signal.score,
            confidence=signal.confidence,
        )

        # Step 4: Orchestrate
        return self.orchestrate(context, trading)

    # ── Gate Evaluation ────────────────────────────────────────

    def _evaluate_gate(
        self,
        gate_name: str,
        gate: Any,
        context: TradingControlContext,
        flow: ControlFlow,
    ) -> Optional[ControlResult]:
        """Evaluate a single gate. Returns None on PASS, result on failure."""
        result = gate.check(context)
        flow.record_gate_result(gate_name, result)

        if not result.passed:
            return result
        return None

    # ── Terminal Handling ──────────────────────────────────────

    def _terminal(self, flow: TradingFlow, result: ControlResult) -> TradingResult:
        """Handle a terminal gate result."""
        cf = flow.control_flow
        status = result.status

        terminal_state_map = {
            GateStatus.REJECT: ControlFlowState.REJECTED,
            GateStatus.BLOCK: ControlFlowState.BLOCKED,
            GateStatus.FREEZE: ControlFlowState.FROZEN,
            GateStatus.EXPIRED: ControlFlowState.EXPIRED,
            GateStatus.ERROR: ControlFlowState.FAILED,
        }

        terminal_state = terminal_state_map.get(status, ControlFlowState.FAILED)
        try:
            if terminal_state == ControlFlowState.REJECTED:
                cf.reject(reason=result.reason, actor=f"{status.name.lower()}-gate")
            elif terminal_state == ControlFlowState.BLOCKED:
                cf.block(reason=result.reason, actor=f"{status.name.lower()}-gate")
            elif terminal_state == ControlFlowState.FROZEN:
                cf.freeze(reason=result.reason, actor=f"{status.name.lower()}-gate")
            elif terminal_state == ControlFlowState.EXPIRED:
                cf.expire(reason=result.reason, actor=f"{status.name.lower()}-gate")
            else:
                cf.fail(reason=result.reason, actor=f"{status.name.lower()}-gate")
        except ValueError:
            pass  # Already in terminal state

        return flow.finalize(terminal_state, result.reason)

    # ── Audit / Query ──────────────────────────────────────────

    @property
    def completed_flows(self) -> List[TradingFlow]:
        return list(self._completed_flows)

    def get_flow(self, flow_id: str) -> Optional[TradingFlow]:
        for f in self._completed_flows:
            if f.flow_id == flow_id:
                return f
        return None

    def flow_count(self) -> int:
        return len(self._completed_flows)

    def reset(self) -> None:
        self._completed_flows.clear()
