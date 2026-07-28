from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExperimentResult:
    """Result of a single experiment iteration."""

    iteration: int
    strategy: str
    metrics: Dict[str, float] = field(default_factory=dict)
    status: str = "finished"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ExperimentLoop:
    """Automated experiment loop that iterates on strategies."""

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.history: List[ExperimentResult] = []

    def run(self, strategy: str) -> ExperimentResult:
        """Run a single experiment iteration on a strategy."""
        result = ExperimentResult(
            iteration=len(self.history) + 1,
            strategy=strategy,
            metrics={"sharpe": 1.0, "ic": 0.05},
            status="finished",
        )
        self.history.append(result)
        return result

    def run_loop(
        self, strategy: str, params_grid: List[Dict[str, Any]]
    ) -> List[ExperimentResult]:
        """Run experiments across a grid of parameters."""
        results = []
        for i, params in enumerate(params_grid):
            if i >= self.max_iterations:
                break
            strategy_name = f"{strategy}_{params}"
            result = self.run(strategy_name)
            result.metrics.update(params)
            results.append(result)
        return results

    def best_result(self) -> Optional[ExperimentResult]:
        """Return the experiment with the highest sharpe ratio."""
        if not self.history:
            return None
        return max(
            self.history,
            key=lambda r: r.metrics.get("sharpe", 0),
        )

    def summary(self) -> Dict[str, Any]:
        if not self.history:
            return {"total_experiments": 0}
        sharpes = [
            r.metrics.get("sharpe", 0) for r in self.history
        ]
        return {
            "total_experiments": len(self.history),
            "best_sharpe": max(sharpes),
            "avg_sharpe": sum(sharpes) / len(sharpes),
            "best_iteration": self.best_result().iteration if self.best_result() else None,
        }
