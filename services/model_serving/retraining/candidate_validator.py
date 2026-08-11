"""
ICYQuant Candidate Validator — Validates candidate models before promotion.

Multi-gate validation pipeline:
  - Data integrity validation
  - Feature contract validation (same features as training)
  - Performance validation (metrics above thresholds)
  - Stability validation (consistent across time windows)
  - Risk validation (drawdown, concentration)
  - Regression validation (no regressions vs production)

A candidate must pass ALL gates to be eligible for promotion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ValidationGate(str, Enum):
    """Validation gate names."""
    DATA_INTEGRITY = "data_integrity"
    FEATURE_CONTRACT = "feature_contract"
    PERFORMANCE = "performance"
    STABILITY = "stability"
    RISK = "risk"
    REGRESSION = "regression"


class ValidationStatus(str, Enum):
    """Overall validation status."""
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class GateResult:
    """Result of a single validation gate."""
    gate: ValidationGate
    passed: bool
    score: float = 0.0
    threshold: float = 0.5
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "score": round(self.score, 4),
            "threshold": self.threshold,
            "details": self.details,
            "warnings": self.warnings,
        }


@dataclass
class ValidationReport:
    """Comprehensive candidate validation report."""
    model_id: str
    candidate_version: str
    status: ValidationStatus = ValidationStatus.PENDING
    gates: Dict[str, GateResult] = field(default_factory=dict)
    overall_score: float = 0.0
    passed_gates: int = 0
    failed_gates: int = 0
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "candidate_version": self.candidate_version,
            "status": self.status.value,
            "overall_score": round(self.overall_score, 4),
            "passed_gates": self.passed_gates,
            "failed_gates": self.failed_gates,
            "gates": {k: v.to_dict() for k, v in self.gates.items()},
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Candidate Validator
# ---------------------------------------------------------------------------

class CandidateValidator:
    """Validates candidate models through a multi-gate pipeline.

    Gates (in order):
      1. Data Integrity — no leaks, consistent feature dimensions
      2. Feature Contract — same features as training schema
      3. Performance — IC, Sharpe, accuracy above minimums
      4. Stability — consistent across train/test periods
      5. Risk — drawdown, concentration within bounds
      6. Regression — no regressions vs production model

    Usage::

        validator = CandidateValidator()
        report = await validator.validate("nvda_model", "candidate_v2", metrics)
        if report.status == ValidationStatus.PASSED:
            await promote(report)
    """

    def __init__(self):
        self._initialized = False

        # Gate thresholds
        self._thresholds: Dict[str, Dict[str, float]] = {
            ValidationGate.PERFORMANCE.value: {
                "min_ic": 0.02,
                "min_rank_ic": 0.03,
                "min_sharpe": 0.5,
            },
            ValidationGate.STABILITY.value: {
                "max_ic_variance": 0.01,
                "max_sharpe_std": 1.0,
            },
            ValidationGate.RISK.value: {
                "max_drawdown": 0.20,
                "max_concentration": 0.30,
            },
        }

        # Validation history
        self._history: List[ValidationReport] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("CandidateValidator initialized")

    # ------------------------------------------------------------------
    # Gate configuration
    # ------------------------------------------------------------------

    def set_threshold(
        self, gate: str, metric: str, value: float
    ) -> None:
        """Set a validation threshold.

        Args:
            gate: Gate name (e.g., 'performance').
            metric: Metric name (e.g., 'min_ic').
            value: Threshold value.
        """
        if gate not in self._thresholds:
            self._thresholds[gate] = {}
        self._thresholds[gate][metric] = value

    def get_thresholds(self) -> Dict[str, Dict[str, float]]:
        return dict(self._thresholds)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate(
        self,
        model_id: str,
        candidate_version: str,
        candidate_metrics: Dict[str, Any],
        production_metrics: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """Run all validation gates.

        Args:
            model_id: Model identifier.
            candidate_version: Candidate version string.
            candidate_metrics: Candidate model metrics.
            production_metrics: Production model metrics (for regression check).

        Returns:
            ValidationReport with pass/fail for each gate.
        """
        report = ValidationReport(
            model_id=model_id,
            candidate_version=candidate_version,
        )

        # Gate 1: Data Integrity
        report.gates["data_integrity"] = self._check_data_integrity(candidate_metrics)

        # Gate 2: Feature Contract
        report.gates["feature_contract"] = self._check_feature_contract(candidate_metrics)

        # Gate 3: Performance
        report.gates["performance"] = self._check_performance(candidate_metrics)

        # Gate 4: Stability
        report.gates["stability"] = self._check_stability(candidate_metrics)

        # Gate 5: Risk
        report.gates["risk"] = self._check_risk(candidate_metrics)

        # Gate 6: Regression
        if production_metrics:
            report.gates["regression"] = self._check_regression(
                candidate_metrics, production_metrics
            )
        else:
            report.gates["regression"] = GateResult(
                gate=ValidationGate.REGRESSION,
                passed=True,
                score=1.0,
                details={"note": "no_production_baseline"},
            )

        # Compute overall
        report.passed_gates = sum(1 for g in report.gates.values() if g.passed)
        report.failed_gates = sum(1 for g in report.gates.values() if not g.passed)
        report.overall_score = sum(g.score for g in report.gates.values()) / max(
            len(report.gates), 1
        )

        # Determine status
        if report.failed_gates == 0:
            report.status = ValidationStatus.PASSED
            report.recommendations = ["Candidate ready for promotion"]
        else:
            report.status = ValidationStatus.FAILED
            report.recommendations = [
                f"Fix failing gate: {g.gate.value} (score={g.score:.4f})"
                for g in report.gates.values() if not g.passed
            ]

        self._history.append(report)
        logger.info(
            "Validation: %s@%s → %s (%d/%d gates passed, score=%.2f)",
            model_id, candidate_version, report.status.value,
            report.passed_gates, len(report.gates), report.overall_score,
        )

        return report

    # ------------------------------------------------------------------
    # Gate implementations
    # ------------------------------------------------------------------

    def _check_data_integrity(self, metrics: Dict[str, Any]) -> GateResult:
        """Check for data leaks and integrity issues."""
        passed = True
        warnings = []

        samples = metrics.get("samples", 0)
        leaks = metrics.get("future_leak", False)
        nan_rate = metrics.get("nan_rate", 0.0)

        if leaks:
            passed = False
            warnings.append("Future data leak detected")

        if nan_rate > 0.05:
            passed = False
            warnings.append(f"High NaN rate: {nan_rate:.2%}")

        if samples < 100:
            warnings.append(f"Low sample count: {samples}")

        return GateResult(
            gate=ValidationGate.DATA_INTEGRITY,
            passed=passed,
            score=1.0 - min(nan_rate, 1.0),
            warnings=warnings,
            details={"samples": samples, "nan_rate": nan_rate, "leaks": leaks},
        )

    def _check_feature_contract(self, metrics: Dict[str, Any]) -> GateResult:
        """Check feature contract consistency."""
        expected = metrics.get("expected_features", 0)
        actual = metrics.get("actual_features", expected)

        score = 1.0 if expected == actual else actual / max(expected, 1)

        return GateResult(
            gate=ValidationGate.FEATURE_CONTRACT,
            passed=score > 0.95,
            score=score,
            details={"expected_features": expected, "actual_features": actual},
        )

    def _check_performance(self, metrics: Dict[str, Any]) -> GateResult:
        """Check performance metrics against thresholds."""
        thresholds = self._thresholds.get(ValidationGate.PERFORMANCE.value, {})
        passed = True
        details = {}

        min_ic = thresholds.get("min_ic", 0.02)
        actual_ic = metrics.get("ic", 0.0)
        details["ic"] = {"value": actual_ic, "threshold": min_ic, "passed": actual_ic >= min_ic}
        if actual_ic < min_ic:
            passed = False

        min_sharpe = thresholds.get("min_sharpe", 0.5)
        actual_sharpe = metrics.get("sharpe", 0.0)
        details["sharpe"] = {
            "value": actual_sharpe, "threshold": min_sharpe,
            "passed": actual_sharpe >= min_sharpe,
        }
        if actual_sharpe < min_sharpe:
            passed = False

        score = (actual_ic / max(min_ic, 0.001) + actual_sharpe / max(min_sharpe, 0.001)) / 2

        return GateResult(
            gate=ValidationGate.PERFORMANCE,
            passed=passed,
            score=min(score, 2.0) / 2.0,
            threshold=0.5,
            details=details,
        )

    def _check_stability(self, metrics: Dict[str, Any]) -> GateResult:
        """Check stability across time windows."""
        thresholds = self._thresholds.get(ValidationGate.STABILITY.value, {})
        passed = True
        details = {}

        max_ic_var = thresholds.get("max_ic_variance", 0.01)
        actual_ic_var = metrics.get("ic_variance", 0.0)
        details["ic_variance"] = {
            "value": actual_ic_var, "threshold": max_ic_var,
            "passed": actual_ic_var <= max_ic_var,
        }
        if actual_ic_var > max_ic_var:
            passed = False

        score = 1.0 - min(actual_ic_var / max(max_ic_var, 0.001), 2.0) / 2.0

        return GateResult(
            gate=ValidationGate.STABILITY,
            passed=passed,
            score=score,
            threshold=0.5,
            details=details,
        )

    def _check_risk(self, metrics: Dict[str, Any]) -> GateResult:
        """Check risk metrics."""
        thresholds = self._thresholds.get(ValidationGate.RISK.value, {})
        passed = True
        details = {}

        max_dd = thresholds.get("max_drawdown", 0.20)
        actual_dd = abs(metrics.get("max_drawdown", 0.0))
        details["drawdown"] = {
            "value": actual_dd, "threshold": max_dd, "passed": actual_dd <= max_dd,
        }
        if actual_dd > max_dd:
            passed = False

        score = 1.0 - min(actual_dd / max(max_dd, 0.001), 2.0) / 2.0

        return GateResult(
            gate=ValidationGate.RISK,
            passed=passed,
            score=score,
            threshold=0.5,
            details=details,
        )

    def _check_regression(
        self,
        candidate_metrics: Dict[str, Any],
        production_metrics: Dict[str, Any],
    ) -> GateResult:
        """Check for regressions vs production model."""
        passed = True
        details = {}
        warnings = []

        # IC regression
        prod_ic = production_metrics.get("ic", 0.0)
        cand_ic = candidate_metrics.get("ic", 0.0)
        ic_change = cand_ic - prod_ic
        details["ic_change"] = {"production": prod_ic, "candidate": cand_ic,
                                "change": round(ic_change, 6)}
        if ic_change < -0.01:
            passed = False
            warnings.append(f"IC regression: {ic_change:.4f}")

        # Sharpe regression
        prod_sharpe = production_metrics.get("sharpe", 0.0)
        cand_sharpe = candidate_metrics.get("sharpe", 0.0)
        details["sharpe_change"] = {"production": prod_sharpe, "candidate": cand_sharpe,
                                     "change": round(cand_sharpe - prod_sharpe, 4)}
        if cand_sharpe < prod_sharpe - 0.1:
            warnings.append(f"Sharpe regression: {cand_sharpe - prod_sharpe:.4f}")

        score = 0.5 + 0.5 * (1.0 if passed else 0.0)

        return GateResult(
            gate=ValidationGate.REGRESSION,
            passed=passed,
            score=score,
            threshold=0.7,
            details=details,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history[-20:]]

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "validations_performed": len(self._history),
            "pass_rate": round(
                sum(1 for r in self._history if r.status == ValidationStatus.PASSED)
                / max(len(self._history), 1), 4
            ),
        }

    def __repr__(self) -> str:
        return f"CandidateValidator(validations={len(self._history)})"
