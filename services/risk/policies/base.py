"""
Risk policy contract.

A single policy is responsible for exactly one check. The pipeline
composition lives in the evaluator, not inside a policy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision


class RiskPolicy(ABC):

    policy_id: str

    @abstractmethod
    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:
        raise NotImplementedError
