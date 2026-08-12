"""
EvaluateTradingGate — run one instruction through the Trading Gate.

This is the single entry point on the order path:

    Strategy Signal → Risk Engine → EvaluateTradingGate → ALLOW/DENY

The command builds a GateContext, evaluates it through the TradingGate
(policy + kill switch), persists the decision snapshot and returns the
evaluation (with any TRADING_BLOCKED / TRADING_GATE_CHANGED events).

The gate never modifies the order — it only decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..trading_gate.gate import GateEvaluation, TradingGate
from ..trading_gate.gate_context import GateContext


@dataclass
class EvaluateTradingGate:
    """Command: evaluate one order request through the Trading Gate."""

    context: GateContext
    gate: TradingGate = field(default_factory=TradingGate)
    correlation_id: str = ""
    now: Optional[datetime] = None

    def execute(self) -> GateEvaluation:
        return self.gate.evaluate(
            self.context,
            correlation_id=self.correlation_id,
            now=self.now,
        )
