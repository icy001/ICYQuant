"""Evolution Evaluator – score and rank strategies in the evolution pool."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .genome import StrategyGenome


@dataclass
class EvaluationResult:
    """Result of evaluating a single strategy genome."""

    genome_name: str
    generation: int = 0

    # Core metrics (from backtest / simulation)
    sharpe_ratio: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    ic_mean: float = 0.0  # information coefficient
    turnover: float = 0.0  # annual turnover

    # Composite scores
    score: float = 0.0  # 0-100 overall score
    risk_score: float = 0.0  # 0-100 risk-adjusted score
    stability_score: float = 0.0  # 0-100 consistency score

    # Ranking
    rank: int = 0
    percentile: float = 0.0

    # Assessment
    grade: str = ""  # "A", "B", "C", "D", "F"
    status: str = ""  # "elite", "keep", "review", "cull"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "genome_name": self.genome_name,
            "generation": self.generation,
            "sharpe_ratio": self.sharpe_ratio,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "ic_mean": self.ic_mean,
            "turnover": self.turnover,
            "score": self.score,
            "risk_score": self.risk_score,
            "stability_score": self.stability_score,
            "rank": self.rank,
            "percentile": self.percentile,
            "grade": self.grade,
            "status": self.status,
            "notes": self.notes,
        }


class EvolutionEvaluator:
    """Evaluates and ranks strategy genomes in the evolution pool.

    Scoring formula:
        Strategy Score = Return Score (0-30) + Risk-Adjusted Score (0-40)
                         + Stability Score (0-30)

    This composite score drives selection: top performers survive,
    poor performers are culled.
    """

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, result: dict) -> dict:
        """Evaluate a single result (legacy interface). Returns simple dict."""
        return {"score": result}

    def evaluate_genome(self, genome: StrategyGenome,
                        metrics: Optional[dict] = None) -> EvaluationResult:
        """Evaluate a strategy genome with given backtest metrics.

        Args:
            genome: The strategy genome to evaluate
            metrics: Dict of backtest results with keys:
                sharpe_ratio, total_return_pct, max_drawdown_pct,
                win_rate, profit_factor, ic_mean, turnover
        """
        m = metrics or {}

        result = EvaluationResult(
            genome_name=genome.name,
            generation=genome.generation,
            sharpe_ratio=m.get("sharpe_ratio", 0.0),
            total_return_pct=m.get("total_return_pct", 0.0),
            max_drawdown_pct=m.get("max_drawdown_pct", 0.0),
            win_rate=m.get("win_rate", 0.0),
            profit_factor=m.get("profit_factor", 0.0),
            ic_mean=m.get("ic_mean", 0.0),
            turnover=m.get("turnover", 0.0),
        )

        # Compute composite score
        result.score = self._compute_score(result)
        result.risk_score = self._compute_risk_score(result)
        result.stability_score = self._compute_stability_score(result)

        # Grade
        result.grade = self._assign_grade(result.score)

        return result

    def evaluate_batch(self, genomes: List[StrategyGenome],
                       metrics_list: Optional[List[dict]] = None
                       ) -> List[EvaluationResult]:
        """Evaluate a batch of genomes and rank them."""
        if metrics_list is None:
            metrics_list = [{}] * len(genomes)

        results = []
        for genome, metrics in zip(genomes, metrics_list):
            result = self.evaluate_genome(genome, metrics)
            results.append(result)

        # Rank by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)
        n = len(results)
        for i, r in enumerate(results):
            r.rank = i + 1
            r.percentile = round((1 - (i / n)) * 100, 1) if n > 0 else 0.0
            r.status = self._assign_status(r.percentile)

        return results

    def rank_and_select(self, results: List[EvaluationResult],
                        top_n: int = 10) -> List[EvaluationResult]:
        """Rank results and select top N candidates."""
        ranked = sorted(results, key=lambda r: r.score, reverse=True)
        return ranked[:top_n]

    def get_population_stats(self, results: List[EvaluationResult]) -> dict:
        """Get summary statistics for a population evaluation."""
        if not results:
            return {"count": 0}

        scores = [r.score for r in results]
        sharpe_ratios = [r.sharpe_ratio for r in results]
        returns = [r.total_return_pct for r in results]
        drawdowns = [r.max_drawdown_pct for r in results]

        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for r in results:
            grade_dist[r.grade] = grade_dist.get(r.grade, 0) + 1

        return {
            "count": len(results),
            "avg_score": round(sum(scores) / len(scores), 1),
            "max_score": round(max(scores), 1),
            "min_score": round(min(scores), 1),
            "avg_sharpe": round(sum(sharpe_ratios) / len(sharpe_ratios), 2),
            "avg_return_pct": round(sum(returns) / len(returns), 2),
            "avg_drawdown_pct": round(sum(drawdowns) / len(drawdowns), 2),
            "grade_distribution": grade_dist,
            "elite_count": sum(1 for r in results if r.status == "elite"),
            "cull_count": sum(1 for r in results if r.status == "cull"),
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(self, r: EvaluationResult) -> float:
        """Compute composite score (0-100)."""
        return_score = self._score_return(r.total_return_pct)
        risk_score = self._score_risk_adjusted(r)
        stability_score = self._score_stability(r)
        total = return_score + risk_score + stability_score
        return round(min(100.0, max(0.0, total)), 1)

    def _score_return(self, return_pct: float) -> float:
        """Score absolute return (0-30)."""
        if return_pct > 50:
            return 30.0
        elif return_pct > 30:
            return 25.0
        elif return_pct > 20:
            return 22.0
        elif return_pct > 10:
            return 18.0
        elif return_pct > 5:
            return 15.0
        elif return_pct > 0:
            return 10.0
        elif return_pct > -5:
            return 5.0
        else:
            return 0.0

    def _score_risk_adjusted(self, r: EvaluationResult) -> float:
        """Score risk-adjusted performance (0-40)."""
        score = 0.0

        # Sharpe ratio component (0-15)
        if r.sharpe_ratio > 3.0:
            score += 15.0
        elif r.sharpe_ratio > 2.0:
            score += 12.0
        elif r.sharpe_ratio > 1.5:
            score += 10.0
        elif r.sharpe_ratio > 1.0:
            score += 7.0
        elif r.sharpe_ratio > 0.5:
            score += 4.0
        elif r.sharpe_ratio > 0:
            score += 2.0

        # Drawdown component (0-15)
        dd = abs(r.max_drawdown_pct)
        if dd < 5:
            score += 15.0
        elif dd < 10:
            score += 12.0
        elif dd < 15:
            score += 8.0
        elif dd < 20:
            score += 5.0
        elif dd < 30:
            score += 2.0

        # Profit factor component (0-10)
        if r.profit_factor > 3.0:
            score += 10.0
        elif r.profit_factor > 2.0:
            score += 8.0
        elif r.profit_factor > 1.5:
            score += 6.0
        elif r.profit_factor > 1.0:
            score += 4.0
        elif r.profit_factor > 0.5:
            score += 2.0

        return score

    def _score_stability(self, r: EvaluationResult) -> float:
        """Score strategy stability (0-30)."""
        score = 0.0

        # Win rate component (0-10)
        if r.win_rate > 0.60:
            score += 10.0
        elif r.win_rate > 0.50:
            score += 8.0
        elif r.win_rate > 0.40:
            score += 5.0
        elif r.win_rate > 0.30:
            score += 3.0

        # IC stability (0-10)
        ic_abs = abs(r.ic_mean)
        if ic_abs > 0.10:
            score += 10.0
        elif ic_abs > 0.05:
            score += 7.0
        elif ic_abs > 0.03:
            score += 4.0
        elif ic_abs > 0.01:
            score += 2.0

        # Turnover (0-10) — lower is more stable
        if r.turnover < 1.0:
            score += 10.0
        elif r.turnover < 3.0:
            score += 7.0
        elif r.turnover < 5.0:
            score += 4.0
        elif r.turnover < 10.0:
            score += 2.0

        return score

    def _compute_risk_score(self, r: EvaluationResult) -> float:
        """Isolated risk score (0-100)."""
        return round(self._score_risk_adjusted(r) * (100 / 40), 1)

    def _compute_stability_score(self, r: EvaluationResult) -> float:
        """Isolated stability score (0-100)."""
        return round(self._score_stability(r) * (100 / 30), 1)

    # ------------------------------------------------------------------
    # Grading & Selection
    # ------------------------------------------------------------------

    def _assign_grade(self, score: float) -> str:
        """Assign a letter grade based on score."""
        if score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 35:
            return "D"
        else:
            return "F"

    def _assign_status(self, percentile: float) -> str:
        """Assign selection status based on percentile."""
        if percentile >= 80:
            return "elite"
        elif percentile >= 50:
            return "keep"
        elif percentile >= 20:
            return "review"
        else:
            return "cull"

    def select_elite(self, results: List[EvaluationResult],
                     max_count: int = 10) -> List[str]:
        """Select elite strategy names for the next generation."""
        elite = [r for r in results if r.status == "elite"]
        elite.sort(key=lambda r: r.score, reverse=True)
        return [r.genome_name for r in elite[:max_count]]

    def select_survivors(self, results: List[EvaluationResult]) -> List[str]:
        """Select survivors (elite + keep) for the next generation."""
        survivors = [r for r in results if r.status in ("elite", "keep")]
        survivors.sort(key=lambda r: r.score, reverse=True)
        return [r.genome_name for r in survivors]
