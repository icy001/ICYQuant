"""Agent Reputation System - tracks and evaluates agent performance."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import defaultdict


class ReputationMetric(Enum):
    """Metrics tracked for agent reputation."""
    PREDICTION_ACCURACY = "PREDICTION_ACCURACY"
    DECISION_QUALITY = "DECISION_QUALITY"
    HISTORICAL_PERFORMANCE = "HISTORICAL_PERFORMANCE"
    RESPONSE_TIME = "RESPONSE_TIME"
    CONSENSUS_ALIGNMENT = "CONSENSUS_ALIGNMENT"
    RISK_AWARENESS = "RISK_AWARENESS"
    LEARNING_RATE = "LEARNING_RATE"


class ReputationTier(Enum):
    """Reputation tier classification."""
    ELITE = "ELITE"
    EXPERT = "EXPERT"
    SENIOR = "SENIOR"
    JUNIOR = "JUNIOR"
    NOVICE = "NOVICE"
    UNRATED = "UNRATED"


@dataclass
class ReputationScore:
    """Detailed reputation score for an agent."""
    agent_id: str
    agent_name: str
    agent_role: str
    overall_score: float
    metrics: Dict[str, float] = field(default_factory=dict)
    tier: ReputationTier = ReputationTier.UNRATED
    total_decisions: int = 0
    correct_decisions: int = 0
    average_confidence: float = 0.0
    trend: str = "STABLE"
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.agent_name,
            "role": self.agent_role,
            "overall_score": self.overall_score,
            "metrics": self.metrics,
            "tier": self.tier.value,
            "total_decisions": self.total_decisions,
            "correct_decisions": self.correct_decisions,
            "accuracy": self.correct_decisions / max(self.total_decisions, 1),
            "avg_confidence": self.average_confidence,
            "trend": self.trend,
        }


@dataclass
class PredictionRecord:
    """Record of a single prediction by an agent."""
    record_id: str
    agent_id: str
    prediction: str
    actual: str
    was_correct: bool
    confidence: float
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class AgentReputationSystem:
    """Tracks and manages agent reputation scores.

    Monitors:
    - Prediction accuracy (87% for Research Agent example)
    - Decision quality over time
    - Historical performance tracking
    - Consensus contribution quality
    - Learning improvement rate

    Reputation influences:
    - Vote weight in consensus decisions
    - Task delegation priority
    - Coordination role assignment
    """

    def __init__(self):
        self.scores: Dict[str, ReputationScore] = {}
        self._predictions: Dict[str, List[PredictionRecord]] = defaultdict(list)
        self._history: Dict[str, List[float]] = defaultdict(list)

    def register_agent(self, agent_id: str, agent_name: str, agent_role: str):
        """Register a new agent for reputation tracking."""
        self.scores[agent_id] = ReputationScore(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_role=agent_role,
            overall_score=0.5,
            metrics={m.value: 0.5 for m in ReputationMetric},
            tier=ReputationTier.NOVICE,
        )

    def update(self, agent_id: str, score: float):
        """Update an agent's overall reputation score."""
        if agent_id in self.scores:
            self.scores[agent_id].overall_score = score
            self._history[agent_id].append(score)
            self._recalculate_tier(agent_id)
            self._update_trend(agent_id)

    def update_metric(self, agent_id: str, metric: ReputationMetric, value: float):
        """Update a specific reputation metric."""
        if agent_id in self.scores:
            self.scores[agent_id].metrics[metric.value] = value
            # Recalculate overall as weighted average of metrics
            weights = {
                ReputationMetric.PREDICTION_ACCURACY: 0.30,
                ReputationMetric.DECISION_QUALITY: 0.25,
                ReputationMetric.HISTORICAL_PERFORMANCE: 0.20,
                ReputationMetric.RESPONSE_TIME: 0.05,
                ReputationMetric.CONSENSUS_ALIGNMENT: 0.10,
                ReputationMetric.RISK_AWARENESS: 0.05,
                ReputationMetric.LEARNING_RATE: 0.05,
            }
            total = 0
            weighted = 0
            for m, v in self.scores[agent_id].metrics.items():
                w = weights.get(ReputationMetric(m), 0.1)
                weighted += v * w
                total += w
            if total > 0:
                self.scores[agent_id].overall_score = weighted / total
            self._recalculate_tier(agent_id)

    def record_prediction(self, agent_id: str, prediction: str, actual: str,
                          confidence: float, context: Dict[str, Any] = None) -> PredictionRecord:
        """Record a prediction and its outcome."""
        if agent_id not in self.scores:
            self.register_agent(agent_id, agent_id, "UNKNOWN")

        was_correct = prediction == actual
        record = PredictionRecord(
            record_id=f"pred_{len(self._predictions[agent_id])}",
            agent_id=agent_id,
            prediction=prediction,
            actual=actual,
            was_correct=was_correct,
            confidence=confidence,
            context=context or {},
        )
        self._predictions[agent_id].append(record)

        # Update accuracy metric
        if self._predictions[agent_id]:
            total = len(self._predictions[agent_id])
            correct = sum(1 for p in self._predictions[agent_id] if p.was_correct)
            accuracy = correct / total
            self.update_metric(agent_id, ReputationMetric.PREDICTION_ACCURACY, accuracy)

        # Update decision stats
        self.scores[agent_id].total_decisions += 1
        if was_correct:
            self.scores[agent_id].correct_decisions += 1

        return record

    def get_reputation(self, agent_id: str) -> Optional[ReputationScore]:
        """Get current reputation for an agent."""
        return self.scores.get(agent_id)

    def get_reputation_weight(self, agent_id: str) -> float:
        """Get voting weight based on reputation."""
        score = self.scores.get(agent_id)
        if not score:
            return 0.1
        return score.overall_score

    def get_top_agents(self, role: str = None, top_n: int = 5) -> List[ReputationScore]:
        """Get top performing agents, optionally filtered by role."""
        agents = list(self.scores.values())
        if role:
            agents = [a for a in agents if a.agent_role == role]
        return sorted(agents, key=lambda a: a.overall_score, reverse=True)[:top_n]

    def get_organization_reputation_summary(self) -> Dict[str, Any]:
        """Get reputation summary for the entire organization."""
        if not self.scores:
            return {"total_agents": 0}

        avg_score = sum(s.overall_score for s in self.scores.values()) / len(self.scores)
        role_avgs = defaultdict(list)
        for s in self.scores.values():
            role_avgs[s.agent_role].append(s.overall_score)

        return {
            "total_agents": len(self.scores),
            "average_score": avg_score,
            "role_averages": {role: sum(scores) / len(scores) for role, scores in role_avgs.items()},
            "tier_distribution": {
                tier.value: sum(1 for s in self.scores.values() if s.tier == tier)
                for tier in ReputationTier
            },
            "top_agent": max(self.scores.values(), key=lambda s: s.overall_score).agent_name
            if self.scores else None,
        }

    def _recalculate_tier(self, agent_id: str):
        """Recalculate reputation tier based on score."""
        score = self.scores[agent_id].overall_score
        if score >= 0.9:
            self.scores[agent_id].tier = ReputationTier.ELITE
        elif score >= 0.75:
            self.scores[agent_id].tier = ReputationTier.EXPERT
        elif score >= 0.6:
            self.scores[agent_id].tier = ReputationTier.SENIOR
        elif score >= 0.4:
            self.scores[agent_id].tier = ReputationTier.JUNIOR
        else:
            self.scores[agent_id].tier = ReputationTier.NOVICE

    def _update_trend(self, agent_id: str):
        """Update reputation trend based on recent history."""
        history = self._history[agent_id]
        if len(history) < 3:
            self.scores[agent_id].trend = "STABLE"
            return
        recent = history[-3:]
        if recent[-1] > recent[0] * 1.05:
            self.scores[agent_id].trend = "IMPROVING"
        elif recent[-1] < recent[0] * 0.95:
            self.scores[agent_id].trend = "DECLINING"
        else:
            self.scores[agent_id].trend = "STABLE"
