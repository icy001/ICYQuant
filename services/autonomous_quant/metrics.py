"""Autonomous Quant Metrics — Prometheus-compatible metrics."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AutonomyMetrics:
    """Metrics for autonomous quant system."""

    research_tasks_total: int = 0
    opportunities_detected_total: int = 0
    hypotheses_generated_total: int = 0
    hypotheses_validated_total: int = 0
    factors_discovered_total: int = 0
    alpha_candidates_total: int = 0
    strategy_candidates_total: int = 0
    autonomous_backtests_total: int = 0
    candidates_promoted_total: int = 0
    candidates_rejected_total: int = 0
    research_compute_budget_remaining: float = 100.0
    research_cycle_latency_ms: float = 0.0

    def to_prometheus(self) -> Dict[str, float]:
        return {
            "icyquant_autonomous_research_tasks_total": self.research_tasks_total,
            "icyquant_opportunities_detected_total": self.opportunities_detected_total,
            "icyquant_hypotheses_generated_total": self.hypotheses_generated_total,
            "icyquant_hypotheses_validated_total": self.hypotheses_validated_total,
            "icyquant_factors_discovered_total": self.factors_discovered_total,
            "icyquant_alpha_candidates_total": self.alpha_candidates_total,
            "icyquant_strategy_candidates_total": self.strategy_candidates_total,
            "icyquant_autonomous_backtests_total": self.autonomous_backtests_total,
            "icyquant_candidates_promoted_total": self.candidates_promoted_total,
            "icyquant_candidates_rejected_total": self.candidates_rejected_total,
            "icyquant_research_compute_budget": self.research_compute_budget_remaining,
            "icyquant_research_cycle_latency": self.research_cycle_latency_ms,
        }
