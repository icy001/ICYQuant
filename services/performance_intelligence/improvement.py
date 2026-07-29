"""Continuous Improvement Engine - root cause analysis and strategy optimization."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ImprovementStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    IN_PROGRESS = "IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class RootCauseCategory(str, Enum):
    STRATEGY_LOGIC = "STRATEGY_LOGIC"
    PARAMETER_MISMATCH = "PARAMETER_MISMATCH"
    MARKET_REGIME = "MARKET_REGIME"
    EXECUTION_QUALITY = "EXECUTION_QUALITY"
    RISK_LIMIT = "RISK_LIMIT"
    DATA_QUALITY = "DATA_QUALITY"
    MODEL_DECAY = "MODEL_DECAY"
    EXTERNAL_FACTOR = "EXTERNAL_FACTOR"


@dataclass
class RootCause:
    cause_id: str
    category: RootCauseCategory
    description: str
    evidence: List[str]
    confidence: float
    impact_score: float


@dataclass
class ImprovementAction:
    action_id: str
    target: str
    current_value: Any
    proposed_value: Any
    expected_impact: float
    priority: int
    status: ImprovementStatus
    rationale: str


@dataclass
class ImprovementPlan:
    plan_id: str
    strategy_name: str
    trigger_event: str
    root_causes: List[RootCause]
    actions: List[ImprovementAction]
    expected_improvement: float
    confidence: float


class ContinuousImprovementEngine:
    """Continuous Improvement Engine.

    Implements: Bad Result → Root Cause Analysis → Parameter Adjustment → Strategy Improvement.
    Drives autonomous strategy optimization.
    """

    def __init__(self):
        self.plans: List[ImprovementPlan] = []
        self.improvement_history: List[Dict[str, Any]] = []

    def improve(self, strategy) -> Dict[str, Any]:
        """Generate improvement recommendations for a strategy.

        Args:
            strategy: Strategy data to improve.

        Returns:
            Dict with improvement plan.
        """
        if isinstance(strategy, dict):
            return self._improve_from_dict(strategy)
        return {"improved": strategy}

    def _improve_from_dict(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Generate improvement plan from structured strategy data."""
        name = strategy.get("name", "Unknown Strategy")
        metrics = strategy.get("metrics", {})

        root_causes = self._identify_root_causes(strategy, metrics)
        actions = self._generate_actions(root_causes, metrics)
        expected_improvement = self._estimate_improvement(actions)

        plan = ImprovementPlan(
            plan_id=f"IMP_{len(self.plans):04d}",
            strategy_name=name,
            trigger_event=strategy.get("trigger_event", "Scheduled review"),
            root_causes=root_causes,
            actions=actions,
            expected_improvement=expected_improvement,
            confidence=self._compute_confidence(root_causes),
        )
        self.plans.append(plan)
        self.improvement_history.append({
            "plan_id": plan.plan_id,
            "strategy": name,
            "root_causes": len(root_causes),
            "actions": len(actions),
            "expected_improvement": expected_improvement,
        })

        return {
            "improved": strategy,
            "improvement_plan": {
                "plan_id": plan.plan_id,
                "strategy_name": name,
                "root_causes": [
                    {
                        "category": rc.category.value,
                        "description": rc.description,
                        "confidence": rc.confidence,
                        "impact_score": rc.impact_score,
                    }
                    for rc in root_causes
                ],
                "actions": [
                    {
                        "target": a.target,
                        "current": str(a.current_value),
                        "proposed": str(a.proposed_value),
                        "expected_impact": a.expected_impact,
                        "priority": a.priority,
                        "rationale": a.rationale,
                    }
                    for a in actions
                ],
                "expected_improvement": expected_improvement,
                "confidence": plan.confidence,
            },
        }

    def _identify_root_causes(self, strategy: Dict, metrics: Dict) -> List[RootCause]:
        """Identify root causes of underperformance."""
        causes = []

        sharpe = metrics.get("sharpe_ratio", 1.0)
        max_dd = metrics.get("max_drawdown", 0.0)
        win_rate = metrics.get("win_rate", 0.5)
        profit_factor = metrics.get("profit_factor", 1.5)

        # Model decay check
        if sharpe < 0.5:
            causes.append(RootCause(
                cause_id=f"RC_{len(causes):04d}",
                category=RootCauseCategory.MODEL_DECAY,
                description="Strategy model may be decaying - Sharpe ratio significantly below threshold",
                evidence=[f"Sharpe: {sharpe:.2f} (< 0.5 threshold)"],
                confidence=0.80,
                impact_score=8.0,
            ))

        # Parameter mismatch
        if win_rate < 0.45:
            causes.append(RootCause(
                cause_id=f"RC_{len(causes):04d}",
                category=RootCauseCategory.PARAMETER_MISMATCH,
                description="Win rate below acceptable threshold - parameter tuning needed",
                evidence=[f"Win rate: {win_rate:.1%} (< 45%)"],
                confidence=0.75,
                impact_score=6.0,
            ))

        # Market regime
        if max_dd > 0.15:
            causes.append(RootCause(
                cause_id=f"RC_{len(causes):04d}",
                category=RootCauseCategory.MARKET_REGIME,
                description="Large drawdown suggests strategy incompatible with current market regime",
                evidence=[f"Max DD: {max_dd:.1%}"],
                confidence=0.70,
                impact_score=7.0,
            ))

        # Risk limit
        if profit_factor < 1.2 and win_rate >= 0.45:
            causes.append(RootCause(
                cause_id=f"RC_{len(causes):04d}",
                category=RootCauseCategory.RISK_LIMIT,
                description="Low profit factor despite adequate win rate - risk limits may be too tight",
                evidence=[f"PF: {profit_factor:.2f}, WR: {win_rate:.1%}"],
                confidence=0.65,
                impact_score=5.0,
            ))

        # If no specific issues found, check general areas
        if not causes:
            causes.append(RootCause(
                cause_id=f"RC_{len(causes):04d}",
                category=RootCauseCategory.STRATEGY_LOGIC,
                description="No clear root cause identified - comprehensive review recommended",
                evidence=["All metrics within acceptable ranges"],
                confidence=0.40,
                impact_score=3.0,
            ))

        return causes

    def _generate_actions(self, causes: List[RootCause],
                          metrics: Dict) -> List[ImprovementAction]:
        """Generate improvement actions based on root causes."""
        actions = []
        priority = 1

        for cause in sorted(causes, key=lambda c: c.impact_score, reverse=True):
            if cause.category == RootCauseCategory.MODEL_DECAY:
                actions.append(ImprovementAction(
                    action_id=f"ACT_{len(actions):04d}",
                    target="model_retraining",
                    current_value="Current model weights",
                    proposed_value="Retrained model with recent data",
                    expected_impact=0.15,
                    priority=priority,
                    status=ImprovementStatus.IDENTIFIED,
                    rationale="Retrain model on most recent 90 days of data",
                ))
            elif cause.category == RootCauseCategory.PARAMETER_MISMATCH:
                current_wr = metrics.get("win_rate", 0.5)
                actions.append(ImprovementAction(
                    action_id=f"ACT_{len(actions):04d}",
                    target="entry_threshold",
                    current_value=f"Current threshold (win_rate={current_wr:.1%})",
                    proposed_value="Increase entry threshold by 20%",
                    expected_impact=0.10,
                    priority=priority,
                    status=ImprovementStatus.IDENTIFIED,
                    rationale="Higher entry threshold should improve win rate",
                ))
            elif cause.category == RootCauseCategory.MARKET_REGIME:
                actions.append(ImprovementAction(
                    action_id=f"ACT_{len(actions):04d}",
                    target="regime_filter",
                    current_value="No regime filter",
                    proposed_value="Add regime detection filter",
                    expected_impact=0.12,
                    priority=priority,
                    status=ImprovementStatus.IDENTIFIED,
                    rationale="Filter signals based on market regime compatibility",
                ))
            elif cause.category == RootCauseCategory.RISK_LIMIT:
                actions.append(ImprovementAction(
                    action_id=f"ACT_{len(actions):04d}",
                    target="risk_limits",
                    current_value="Current risk limits",
                    proposed_value="Relax risk limits by 15% for high-conviction trades",
                    expected_impact=0.08,
                    priority=priority,
                    status=ImprovementStatus.IDENTIFIED,
                    rationale="Selectively increase risk budget for strongest signals",
                ))
            elif cause.category == RootCauseCategory.STRATEGY_LOGIC:
                actions.append(ImprovementAction(
                    action_id=f"ACT_{len(actions):04d}",
                    target="strategy_review",
                    current_value="Current strategy logic",
                    proposed_value="Comprehensive logic review",
                    expected_impact=0.05,
                    priority=priority,
                    status=ImprovementStatus.IDENTIFIED,
                    rationale="Manual review of strategy logic and assumptions",
                ))
            priority += 1

        return actions

    def _estimate_improvement(self, actions: List[ImprovementAction]) -> float:
        if not actions:
            return 0.0
        # Diminishing returns on multiple actions
        total = 0.0
        weight = 1.0
        for a in sorted(actions, key=lambda x: x.expected_impact, reverse=True):
            total += a.expected_impact * weight
            weight *= 0.7
        return min(0.5, total)

    def _compute_confidence(self, causes: List[RootCause]) -> float:
        if not causes:
            return 0.5
        return sum(c.confidence for c in causes) / len(causes)

    def get_latest_plan(self) -> Optional[ImprovementPlan]:
        """Get the most recent improvement plan."""
        return self.plans[-1] if self.plans else None

    def get_pending_actions(self) -> List[ImprovementAction]:
        """Get all improvement actions that are not yet verified."""
        if not self.plans:
            return []
        return [a for p in self.plans
                for a in p.actions
                if a.status != ImprovementStatus.VERIFIED]
