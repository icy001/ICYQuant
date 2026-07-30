"""
Continuous Evaluation Engine.

Post-training quality gates that evaluate newly trained models
against a comprehensive set of metrics before allowing promotion.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GateStatus(str, enum.Enum):
    """Result of a quality gate check."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EvaluationConfig:
    """Configuration for continuous evaluation."""

    # Metric thresholds for quality gates
    sharpe_min: float = 1.0
    sortino_min: float = 0.8
    max_drawdown_max: float = 0.25
    ic_min: float = 0.03
    rank_ic_min: float = 0.02
    turnover_max: float = 0.5
    win_rate_min: float = 0.52

    # Composite scoring weights (must sum to 1.0)
    metric_weights: Dict[str, float] = field(default_factory=lambda: {
        "sharpe": 0.30,
        "sortino": 0.20,
        "max_drawdown": 0.15,
        "ic": 0.15,
        "rank_ic": 0.10,
        "win_rate": 0.10,
    })

    # Gate thresholds
    pass_score: float = 70.0  # Minimum composite score to pass
    warn_score: float = 50.0  # Below this is FAIL

    # Requirements
    require_walk_forward: bool = True
    require_out_of_sample: bool = True
    min_out_of_sample_months: int = 6

    # Auto-promotion
    auto_promote_on_pass: bool = False
    require_approval: bool = True


@dataclass
class EvaluationGate:
    """A single quality gate check result."""

    name: str
    status: GateStatus = GateStatus.PENDING
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result for a model."""

    eval_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    model_version: str = ""

    # Timing
    evaluated_at: float = field(default_factory=time.time)
    data_period_start: Optional[str] = None
    data_period_end: Optional[str] = None

    # Raw metrics
    metrics: Dict[str, float] = field(default_factory=dict)

    # Composite score
    composite_score: float = 0.0
    overall_status: GateStatus = GateStatus.PENDING

    # Individual gates
    gates: List[EvaluationGate] = field(default_factory=list)

    # Walk-forward
    walk_forward_passed: bool = False

    # Out-of-sample
    out_of_sample_passed: bool = False

    # Recommendations
    recommendation: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "evaluated_at": self.evaluated_at,
            "data_period_start": self.data_period_start,
            "data_period_end": self.data_period_end,
            "metrics": self.metrics,
            "composite_score": self.composite_score,
            "overall_status": self.overall_status.value,
            "gates": [g.to_dict() for g in self.gates],
            "walk_forward_passed": self.walk_forward_passed,
            "out_of_sample_passed": self.out_of_sample_passed,
            "recommendation": self.recommendation,
            "warnings": self.warnings,
        }


@dataclass
class EvaluationJob:
    """Tracks an evaluation run."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    model_version: str = ""
    status: GateStatus = GateStatus.PENDING
    result: Optional[EvaluationResult] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# ---------------------------------------------------------------------------
# Continuous Evaluator
# ---------------------------------------------------------------------------

class ContinuousEvaluator:
    """Post-training model evaluator with quality gates.

    Evaluates models on Sharpe, Sortino, Max Drawdown, IC, Rank IC,
    Turnover, and Win Rate. Produces a composite score and PASS/WARN/FAIL
    status. Only PASS models are eligible for promotion.

    Usage::

        evaluator = ContinuousEvaluator(config)
        result = evaluator.evaluate("Alpha_v39", metrics)
        if result.overall_status == GateStatus.PASS:
            # promote to staging
    """

    # Standard metric names
    SHARPE = "sharpe"
    SORTINO = "sortino"
    MAX_DRAWDOWN = "max_drawdown"
    IC = "ic"
    RANK_IC = "rank_ic"
    TURNOVER = "turnover"
    WIN_RATE = "win_rate"

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self._history: List[EvaluationResult] = []
        self._baselines: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model_name: str,
        model_version: str,
        metrics: Dict[str, float],
        walk_forward_result: Optional[Dict[str, Any]] = None,
        out_of_sample_result: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate a model against quality gates.

        Args:
            model_name: Name of the model.
            model_version: Version identifier.
            metrics: Dict of metric name → value.
            walk_forward_result: Optional walk-forward validation result.
            out_of_sample_result: Optional out-of-sample test result.

        Returns:
            EvaluationResult with gate statuses and composite score.
        """
        result = EvaluationResult(
            model_name=model_name,
            model_version=model_version,
            metrics=dict(metrics),
        )

        gates: List[EvaluationGate] = []

        # --- Individual metric gates ---
        gates.append(self._check_gate(
            self.SHARPE, metrics.get(self.SHARPE, 0),
            self.config.sharpe_min, higher_is_better=True,
        ))
        gates.append(self._check_gate(
            self.SORTINO, metrics.get(self.SORTINO, 0),
            self.config.sortino_min, higher_is_better=True,
        ))
        gates.append(self._check_gate(
            self.MAX_DRAWDOWN, metrics.get(self.MAX_DRAWDOWN, 1),
            self.config.max_drawdown_max, higher_is_better=False,
        ))
        gates.append(self._check_gate(
            self.IC, metrics.get(self.IC, 0),
            self.config.ic_min, higher_is_better=True,
        ))
        gates.append(self._check_gate(
            self.RANK_IC, metrics.get(self.RANK_IC, 0),
            self.config.rank_ic_min, higher_is_better=True,
        ))
        gates.append(self._check_gate(
            self.TURNOVER, metrics.get(self.TURNOVER, 1),
            self.config.turnover_max, higher_is_better=False,
        ))
        gates.append(self._check_gate(
            self.WIN_RATE, metrics.get(self.WIN_RATE, 0),
            self.config.win_rate_min, higher_is_better=True,
        ))

        result.gates = gates

        # --- Composite score ---
        result.composite_score = self._compute_composite_score(metrics)

        # --- Walk-forward gate ---
        if self.config.require_walk_forward:
            result.walk_forward_passed = self._check_walk_forward(walk_forward_result)
            if not result.walk_forward_passed:
                result.warnings.append("Walk-forward validation not passed")

        # --- Out-of-sample gate ---
        if self.config.require_out_of_sample:
            result.out_of_sample_passed = self._check_out_of_sample(out_of_sample_result)
            if not result.out_of_sample_passed:
                result.warnings.append("Out-of-sample validation not passed")

        # --- Overall status ---
        result.overall_status = self._determine_overall_status(result)

        # --- Recommendation ---
        result.recommendation = self._generate_recommendation(result)

        self._history.append(result)
        logger.info(
            f"Evaluation {result.eval_id}: {model_name} v{model_version} "
            f"score={result.composite_score:.1f}, status={result.overall_status.value}"
        )

        return result

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(
        self, result_a: EvaluationResult, result_b: EvaluationResult
    ) -> Dict[str, Any]:
        """Compare two evaluation results and declare a winner.

        Returns:
            Dict with 'winner', 'margin', and per-metric comparisons.
        """
        comparison = {
            "model_a": result_a.model_name,
            "model_b": result_b.model_name,
            "score_a": result_a.composite_score,
            "score_b": result_b.composite_score,
            "metrics": {},
        }

        for metric in set(list(result_a.metrics.keys()) + list(result_b.metrics.keys())):
            va = result_a.metrics.get(metric, 0)
            vb = result_b.metrics.get(metric, 0)
            comparison["metrics"][metric] = {
                "a": va, "b": vb, "diff": vb - va,
            }

        if result_a.composite_score > result_b.composite_score:
            comparison["winner"] = result_a.model_name
            comparison["margin"] = result_a.composite_score - result_b.composite_score
        elif result_b.composite_score > result_a.composite_score:
            comparison["winner"] = result_b.model_name
            comparison["margin"] = result_b.composite_score - result_a.composite_score
        else:
            comparison["winner"] = "tie"
            comparison["margin"] = 0.0

        return comparison

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------

    def set_baseline(self, model_name: str, metrics: Dict[str, float]) -> None:
        """Set baseline metrics for a model (e.g., from training)."""
        self._baselines[model_name] = dict(metrics)

    def compare_to_baseline(
        self, model_name: str, current_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Compare current metrics to stored baseline."""
        baseline = self._baselines.get(model_name, {})
        diffs = {}
        for k in set(list(baseline.keys()) + list(current_metrics.keys())):
            diffs[k] = {
                "baseline": baseline.get(k, 0),
                "current": current_metrics.get(k, 0),
                "change_pct": (
                    (current_metrics.get(k, 0) - baseline.get(k, 0)) / abs(baseline.get(k, 0.001))
                    if abs(baseline.get(k, 0.001)) > 1e-9 else 0
                ),
            }
        return {"model": model_name, "comparisons": diffs}

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(
        self, model_name: Optional[str] = None, limit: int = 50
    ) -> List[EvaluationResult]:
        """Get evaluation history, optionally filtered by model."""
        results = self._history
        if model_name:
            results = [r for r in results if r.model_name == model_name]
        return sorted(results, key=lambda r: r.evaluated_at, reverse=True)[:limit]

    def get_latest(self, model_name: str) -> Optional[EvaluationResult]:
        """Get the most recent evaluation for a model."""
        for r in sorted(self._history, key=lambda x: x.evaluated_at, reverse=True):
            if r.model_name == model_name:
                return r
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_gate(
        self, name: str, value: float, threshold: float, higher_is_better: bool
    ) -> EvaluationGate:
        """Check a single metric against its threshold."""
        if higher_is_better:
            passed = value >= threshold
        else:
            passed = value <= threshold

        if passed:
            status = GateStatus.PASS
            msg = f"{name}={value:.4f} >= threshold={threshold}" if higher_is_better else f"{name}={value:.4f} <= threshold={threshold}"
        else:
            status = GateStatus.FAIL
            msg = f"{name}={value:.4f} {'<' if higher_is_better else '>'} threshold={threshold}"

        return EvaluationGate(name=name, status=status, value=value, threshold=threshold, message=msg)

    def _compute_composite_score(self, metrics: Dict[str, float]) -> float:
        """Compute weighted composite score (0-100)."""
        score = 0.0
        total_weight = 0.0

        # Normalize each metric to a 0-100 scale
        normalizers = {
            self.SHARPE: lambda v: min(v / 3.0 * 100, 100),  # 3.0 → 100
            self.SORTINO: lambda v: min(v / 3.0 * 100, 100),
            self.MAX_DRAWDOWN: lambda v: max((1.0 - v) * 100, 0),  # lower is better
            self.IC: lambda v: min(v / 0.1 * 100, 100),  # 0.1 → 100
            self.RANK_IC: lambda v: min(v / 0.1 * 100, 100),
            self.TURNOVER: lambda v: max((1.0 - v) * 100, 0),
            self.WIN_RATE: lambda v: v * 100,
        }

        for metric_name, weight in self.config.metric_weights.items():
            if metric_name in metrics:
                normalizer = normalizers.get(metric_name, lambda v: v * 100)
                normalized = normalizer(metrics[metric_name])
                score += normalized * weight
                total_weight += weight

        if total_weight > 0:
            score /= total_weight

        return round(score, 1)

    def _check_walk_forward(self, wf_result: Optional[Dict[str, Any]]) -> bool:
        """Check if walk-forward validation passed."""
        if wf_result is None:
            return not self.config.require_walk_forward
        return wf_result.get("passed", wf_result.get("status") == "PASS")

    def _check_out_of_sample(self, oos_result: Optional[Dict[str, Any]]) -> bool:
        """Check if out-of-sample validation passed."""
        if oos_result is None:
            return not self.config.require_out_of_sample
        return oos_result.get("passed", oos_result.get("status") == "PASS")

    def _determine_overall_status(self, result: EvaluationResult) -> GateStatus:
        """Determine overall PASS/WARN/FAIL from individual gates."""
        # Any FAIL gate → overall FAIL
        for gate in result.gates:
            if gate.status == GateStatus.FAIL:
                return GateStatus.FAIL

        # Walk-forward / OOS required but not passed
        if self.config.require_walk_forward and not result.walk_forward_passed:
            return GateStatus.FAIL
        if self.config.require_out_of_sample and not result.out_of_sample_passed:
            return GateStatus.FAIL

        # Score-based
        if result.composite_score >= self.config.pass_score:
            return GateStatus.PASS
        elif result.composite_score >= self.config.warn_score:
            return GateStatus.WARN
        else:
            return GateStatus.FAIL

    def _generate_recommendation(self, result: EvaluationResult) -> str:
        """Generate a human-readable recommendation."""
        if result.overall_status == GateStatus.PASS:
            msg = f"Model passes all gates (score={result.composite_score:.1f}). "
            msg += "Eligible for promotion." if not self.config.require_approval else "Ready for approval review."
        elif result.overall_status == GateStatus.WARN:
            failed_gates = [g.name for g in result.gates if g.status == GateStatus.FAIL]
            msg = f"Model has warnings (score={result.composite_score:.1f}). "
            if failed_gates:
                msg += f"Failed gates: {failed_gates}. "
            msg += "Review recommended before promotion."
        else:
            failed_gates = [g.name for g in result.gates if g.status == GateStatus.FAIL]
            msg = f"Model FAILED evaluation (score={result.composite_score:.1f}). "
            msg += f"Failed gates: {failed_gates}. "
            msg += "Do NOT promote."
        return msg

    def reset(self) -> None:
        """Reset evaluator state (for testing)."""
        self._history.clear()
        self._baselines.clear()
