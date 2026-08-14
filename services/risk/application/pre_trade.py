"""Pre-trade risk checking (Commit 37 Part 1.5).

``PreTradeRiskContext`` carries everything a risk rule may need about the
order and its environment; ``PreTradeRiskChecker`` is the entry point that
runs every configured rule and aggregates the resulting decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.risk.application.decision_aggregator import (
    RiskDecisionAggregator,
)
from services.risk.domain.decision import RiskDecision


@dataclass(frozen=True)
class PreTradeRiskContext:
    order: Any
    portfolio: Any | None = None
    market: Any | None = None
    account: Any | None = None


class PreTradeRiskChecker:
    """
    Entry point for pre-trade risk validation.
    """

    def __init__(
        self,
        rules: list[Any],
        aggregator: RiskDecisionAggregator | None = None,
    ) -> None:
        self._rules = tuple(rules)
        self._aggregator = aggregator or RiskDecisionAggregator()

    def check(
        self,
        context: PreTradeRiskContext,
    ) -> RiskDecision:

        decisions: list[RiskDecision] = []

        for rule in self._rules:
            decision = rule.evaluate(context)

            if decision is not None:
                decisions.append(decision)

        return self._aggregator.aggregate(decisions)
