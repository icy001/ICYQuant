"""
Integration Service — Institutional Trading Control Flow.

Commit 21 Part 1.1 — establishes the unified institutional trading control
flow connecting Strategy, Risk, Governance, Authority, Approval, and Order.

This is the Integration Layer that ensures no order bypasses institutional controls.
"""

from .control_state import (
    ControlFlowState,
    VALID_CONTROL_TRANSITIONS,
    can_transition,
    valid_transitions_from,
    is_fail_closed_state,
)
from .control_context import TradingControlContext
from .control_transition import ControlTransition
from .control_result import ControlResult, GateStatus
from .control_flow import ControlFlow

from .trading_context import TradingContext
from .trading_transition import TradingTransition, TradingTransitionType
from .trading_result import TradingResult, TradingOutcome
from .trading_flow import TradingFlow

from .control_gate import ControlGate
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

from .flow_orchestrator import FlowOrchestrator
from .flow_validator import FlowValidator, FlowValidationResult, InvariantViolation
from .flow_registry import FlowRegistry
from .integration_metrics import IntegrationMetrics, FlowMetrics, GateMetrics

__all__ = [
    # ── Control Flow ───────────────────────────────────────────
    "ControlFlowState",
    "VALID_CONTROL_TRANSITIONS",
    "can_transition",
    "valid_transitions_from",
    "is_fail_closed_state",
    "ControlTransition",
    "ControlResult",
    "GateStatus",
    "TradingControlContext",
    "ControlFlow",
    # ── Trading Flow ───────────────────────────────────────────
    "TradingContext",
    "TradingTransition",
    "TradingTransitionType",
    "TradingResult",
    "TradingOutcome",
    "TradingFlow",
    # ── Gates ──────────────────────────────────────────────────
    "ControlGate",
    "RiskGate",
    "RiskGateConfig",
    "GovernanceGate",
    "AuthorityGate",
    "ApprovalGate",
    # ── Adapters ───────────────────────────────────────────────
    "SignalAdapter",
    "SignalInput",
    "DecisionAdapter",
    "RiskAdapter",
    "GovernanceAdapter",
    "AuthorityAdapter",
    "ApprovalAdapter",
    "OrderAdapter",
    "OrderIntent",
    # ── Orchestration ──────────────────────────────────────────
    "FlowOrchestrator",
    "FlowValidator",
    "FlowValidationResult",
    "InvariantViolation",
    "FlowRegistry",
    "IntegrationMetrics",
    "FlowMetrics",
    "GateMetrics",
]
