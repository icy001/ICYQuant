from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .experiment import ExperimentResult


@dataclass
class EvaluationReport:
    """Structured evaluation of a research experiment."""

    result: ExperimentResult
    score: float = 0.0
    decision: str = "CONTINUE"
    reason: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)


class ResearchEvaluator:
    """Evaluates experiment results and makes go/no-go decisions."""

    def __init__(
        self,
        min_sharpe: float = 0.3,
        min_ic: float = 0.01,
        good_sharpe: float = 0.8,
    ):
        self.min_sharpe = min_sharpe
        self.min_ic = min_ic
        self.good_sharpe = good_sharpe

    def evaluate(self, result: ExperimentResult) -> EvaluationReport:
        """Evaluate an experiment result and produce a decision."""
        sharpe = result.metrics.get("sharpe", 0)
        ic = result.metrics.get("ic", 0)

        if sharpe < self.min_sharpe:
            decision = "DISCARD"
            reason = f"Sharpe {sharpe} below minimum {self.min_sharpe}"
            score = 0.1
        elif sharpe < self.good_sharpe:
            decision = "CONTINUE"
            reason = f"Sharpe {sharpe} acceptable, continue optimizing"
            score = 0.5
        else:
            decision = "ACCEPT"
            reason = f"Sharpe {sharpe} exceeds target {self.good_sharpe}"
            score = 1.0

        if ic < self.min_ic:
            decision = "DISCARD"
            reason = f"IC {ic} below minimum {self.min_ic}"
            score = 0.0

        return EvaluationReport(
            result=result,
            score=score,
            decision=decision,
            reason=reason,
            metrics={
                "sharpe": sharpe,
                "ic": ic,
            },
        )

    def evaluate_all(
        self, results: List[ExperimentResult]
    ) -> List[EvaluationReport]:
        """Evaluate multiple experiment results."""
        return [self.evaluate(r) for r in results]

    def best_decision(
        self, reports: List[EvaluationReport]
    ) -> Optional[EvaluationReport]:
        """Find the best accepted or continued result."""
        accepted = [r for r in reports if r.decision == "ACCEPT"]
        if accepted:
            return max(accepted, key=lambda r: r.score)
        continued = [r for r in reports if r.decision == "CONTINUE"]
        if continued:
            return max(continued, key=lambda r: r.score)
        return None
