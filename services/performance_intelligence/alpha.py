"""Alpha Attribution Engine - identifies true alpha vs beta vs luck."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AlphaSource(str, Enum):
    TRUE_ALPHA = "TRUE_ALPHA"
    BETA = "BETA"
    SMART_BETA = "SMART_BETA"
    LUCK = "LUCK"
    LEVERAGE = "LEVERAGE"
    CONCENTRATION = "CONCENTRATION"


class AlphaConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class AlphaComponent:
    source: AlphaSource
    contribution: float
    t_statistic: float
    persistence_score: float
    explanation: str


@dataclass
class AlphaReport:
    report_id: str
    total_alpha: float
    components: List[AlphaComponent]
    alpha_ratio: float
    confidence: AlphaConfidence
    is_statistically_significant: bool


class AlphaAttributionEngine:
    """Alpha Attribution Engine.

    Identifies: True Alpha vs Beta Return vs Luck Component.
    Separates genuine skill from market exposure and randomness.
    """

    def __init__(self):
        self.reports: List[AlphaReport] = []

    def analyze(self, performance) -> Dict[str, Any]:
        """Analyze performance to attribute alpha sources.

        Args:
            performance: Performance data to analyze.

        Returns:
            Dict with alpha attribution.
        """
        if isinstance(performance, dict):
            return self._analyze_from_dict(performance)
        return {"alpha": performance}

    def _analyze_from_dict(self, performance: Dict[str, Any]) -> Dict[str, Any]:
        """Perform alpha attribution from structured data."""
        total_return = performance.get("total_return", 0.0)
        benchmark_return = performance.get("benchmark_return", 0.0)
        beta = performance.get("beta", 1.0)
        risk_free = performance.get("risk_free_rate", 0.02)
        track_record_length = performance.get("track_record_length", 252)

        raw_excess = total_return - risk_free
        market_excess = benchmark_return - risk_free

        # Expected return from beta exposure
        beta_return = beta * market_excess

        # Residual (potential alpha)
        residual = raw_excess - beta_return

        components = []

        # Beta component
        components.append(AlphaComponent(
            source=AlphaSource.BETA,
            contribution=beta_return,
            t_statistic=beta / 0.15 if beta > 0 else 0.0,
            persistence_score=0.95,
            explanation=f"Beta ({beta:.2f}) contributed {beta_return:.4f} to excess return",
        ))

        # True alpha assessment
        alpha_t_stat = self._compute_alpha_t_stat(residual, performance.get("volatility", 0.15),
                                                   track_record_length)
        is_significant = abs(alpha_t_stat) > 2.0

        alpha_persistence = self._estimate_alpha_persistence(performance.get("rolling_alphas", []))
        components.append(AlphaComponent(
            source=AlphaSource.TRUE_ALPHA,
            contribution=residual if is_significant else residual * 0.5,
            t_statistic=alpha_t_stat,
            persistence_score=alpha_persistence,
            explanation=f"True alpha estimate: {residual:.4f} (t-stat: {alpha_t_stat:.2f})",
        ))

        # Smart beta component
        smart_beta = performance.get("smart_beta_contribution", 0.0)
        components.append(AlphaComponent(
            source=AlphaSource.SMART_BETA,
            contribution=smart_beta,
            t_statistic=1.5,
            persistence_score=0.70,
            explanation=f"Smart beta factors contributed {smart_beta:.4f}",
        ))

        # Luck component
        luck = max(0.0, residual * 0.3) if not is_significant else max(0.0, residual * 0.1)
        components.append(AlphaComponent(
            source=AlphaSource.LUCK,
            contribution=luck,
            t_statistic=0.5,
            persistence_score=0.10,
            explanation=f"Estimated luck/noise component: {luck:.4f}",
        ))

        # Confidence determination
        if is_significant and alpha_persistence > 0.7:
            confidence = AlphaConfidence.HIGH
        elif is_significant or alpha_persistence > 0.5:
            confidence = AlphaConfidence.MEDIUM
        else:
            confidence = AlphaConfidence.LOW

        alpha_ratio = residual / raw_excess if raw_excess != 0 else 0.0

        report = AlphaReport(
            report_id=f"ALPHA_{len(self.reports):04d}",
            total_alpha=residual,
            components=components,
            alpha_ratio=alpha_ratio,
            confidence=confidence,
            is_statistically_significant=is_significant,
        )
        self.reports.append(report)

        return {
            "alpha": performance,
            "total_alpha": residual,
            "alpha_ratio": alpha_ratio,
            "confidence": confidence.value,
            "is_statistically_significant": is_significant,
            "components": [
                {"source": c.source.value, "contribution": c.contribution,
                 "t_statistic": c.t_statistic, "persistence": c.persistence_score,
                 "explanation": c.explanation}
                for c in components
            ],
            "assessment": self._generate_assessment(report),
        }

    def _compute_alpha_t_stat(self, alpha: float, volatility: float, periods: int) -> float:
        if volatility <= 0 or periods <= 0:
            return 0.0
        se = volatility / (periods ** 0.5)
        return alpha / se if se > 0 else 0.0

    def _estimate_alpha_persistence(self, rolling_alphas: List[float]) -> float:
        if not rolling_alphas or len(rolling_alphas) < 2:
            return 0.5
        positive_count = sum(1 for a in rolling_alphas if a > 0)
        return positive_count / len(rolling_alphas)

    def _generate_assessment(self, report: AlphaReport) -> str:
        if report.confidence == AlphaConfidence.HIGH:
            return "Strong evidence of genuine alpha generation capability"
        elif report.confidence == AlphaConfidence.MEDIUM:
            return "Moderate evidence of alpha - requires more track record"
        elif report.confidence == AlphaConfidence.LOW:
            return "Returns largely explained by beta - limited alpha evidence"
        return "Insufficient data for alpha assessment"

    def get_latest_report(self) -> Optional[AlphaReport]:
        """Get the most recent alpha attribution report."""
        return self.reports[-1] if self.reports else None

    def get_significant_alphas(self) -> List[AlphaReport]:
        """Get all reports with statistically significant alpha."""
        return [r for r in self.reports if r.is_statistically_significant]
