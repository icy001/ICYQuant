"""Trading Gate — the single production trading permission boundary.

The gate answers exactly one question per order request:

    Can this trading instruction proceed?

The result is strictly ALLOW or DENY — there is no "maybe" on the order path.
Every decision is recorded as a :class:`GateDecisionRecord` (decision snapshot
+ policy version) for auditability.

The gate never modifies orders, positions or risk state — it is a pure
decision boundary.
"""

from .gate import GateEvaluation, TradingGate
from .gate_context import GateContext, OrderContext, RiskDecision
from .gate_decision import (
    GateDecision,
    GateDecisionRecord,
    GateSeverity,
)
from .gate_policy import GatePolicy
from .gate_reason import GateReason

__all__ = [
    "GateContext",
    "GateDecision",
    "GateDecisionRecord",
    "GateEvaluation",
    "GatePolicy",
    "GateReason",
    "GateSeverity",
    "OrderContext",
    "RiskDecision",
    "TradingGate",
]
