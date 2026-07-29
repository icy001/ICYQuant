"""Organization Learning Engine - enables the AI organization to learn and improve."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


class LearningDomain(Enum):
    """Domain of organizational learning."""
    PROCESS_EFFICIENCY = "PROCESS_EFFICIENCY"
    DECISION_QUALITY = "DECISION_QUALITY"
    AGENT_COLLABORATION = "AGENT_COLLABORATION"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    COMMUNICATION = "COMMUNICATION"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"


class ImprovementType(Enum):
    """Type of organizational improvement."""
    STRUCTURAL = "STRUCTURAL"
    PROCEDURAL = "PROCEDURAL"
    AGENT_SPECIFIC = "AGENT_SPECIFIC"
    SYSTEMIC = "SYSTEMIC"


@dataclass
class LearningObservation:
    """A single observation for organizational learning."""
    observation_id: str
    domain: LearningDomain
    description: str
    source_agents: List[str]
    impact: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class OrganizationInsight:
    """An insight derived from organizational learning."""
    insight_id: str
    domain: LearningDomain
    finding: str
    confidence: float
    supporting_observations: int
    action_required: bool
    recommendation: str


@dataclass
class LearningReport:
    """Report on organizational learning progress."""
    total_observations: int
    insights_generated: int
    improvements_made: int
    domains_analyzed: List[str]
    key_findings: List[str]
    organization_score: float
    trend: str
    recommendations: List[str]
    next_actions: List[str]


class OrganizationLearningEngine:
    """Engine for organizational learning and continuous improvement.

    Analyzes:
    - Agent collaboration patterns
    - Decision quality over time
    - Process efficiency metrics
    - Communication effectiveness

    Continuously optimizes the AI organization structure.

    Learning loop:
    ```
    Observe → Analyze → Learn → Improve → Repeat
    ```
    """

    def __init__(self):
        self._observations: List[LearningObservation] = []
        self._insights: List[OrganizationInsight] = []
        self._improvements: List[Dict[str, Any]] = []
        self._metrics: Dict[str, List[float]] = defaultdict(list)
        self._counter = 0

    def learn(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Learn from an organizational result.

        Args:
            result: The result to learn from.

        Returns:
            Dict with learning outcomes.
        """
        # Extract observations from result
        observations = self._extract_observations(result)
        for obs in observations:
            self._observations.append(obs)

        # Generate insights
        new_insights = self._generate_insights()
        for insight in new_insights:
            self._insights.append(insight)

        # Track metrics
        self._track_metrics(result)

        return {
            "learning": result,
            "observations_extracted": len(observations),
            "new_insights": len(new_insights),
            "total_observations": len(self._observations),
            "total_insights": len(self._insights),
        }

    def record_observation(self, domain: LearningDomain, description: str,
                           source_agents: List[str], impact: float,
                           evidence: Dict[str, Any] = None) -> LearningObservation:
        """Record a learning observation."""
        self._counter += 1
        obs = LearningObservation(
            observation_id=f"obs_{self._counter}",
            domain=domain,
            description=description,
            source_agents=source_agents,
            impact=impact,
            evidence=evidence or {},
        )
        self._observations.append(obs)
        return obs

    def record_improvement(self, improvement_type: ImprovementType, description: str,
                           agents_affected: List[str], result: Dict[str, Any]):
        """Record an organizational improvement."""
        self._improvements.append({
            "type": improvement_type.value,
            "description": description,
            "agents_affected": agents_affected,
            "result": result,
        })

    def generate_report(self) -> LearningReport:
        """Generate a comprehensive organizational learning report."""
        observations = len(self._observations)
        insights = len(self._insights)
        improvements = len(self._improvements)

        domains = list(set(o.domain.value for o in self._observations))
        key_findings = self._get_key_findings()

        # Calculate organization score
        org_score = self._calculate_organization_score()

        # Determine trend
        trend = self._determine_trend()

        return LearningReport(
            total_observations=observations,
            insights_generated=insights,
            improvements_made=improvements,
            domains_analyzed=domains,
            key_findings=key_findings,
            organization_score=org_score,
            trend=trend,
            recommendations=self._generate_recommendations(),
            next_actions=self._generate_next_actions(),
        )

    def get_domain_insights(self, domain: LearningDomain) -> List[OrganizationInsight]:
        """Get insights for a specific learning domain."""
        return [i for i in self._insights if i.domain == domain]

    def get_improvement_history(self) -> List[Dict[str, Any]]:
        """Get history of organizational improvements."""
        return self._improvements

    def get_organization_health(self) -> Dict[str, Any]:
        """Get organization health metrics."""
        return {
            "observations": len(self._observations),
            "insights": len(self._insights),
            "improvements": len(self._improvements),
            "avg_observation_impact": (
                sum(o.impact for o in self._observations) / len(self._observations)
                if self._observations else 0
            ),
            "domains_active": len(set(o.domain for o in self._observations)),
            "insights_with_action": sum(1 for i in self._insights if i.action_required),
            "trend": self._determine_trend(),
        }

    def _extract_observations(self, result: Dict[str, Any]) -> List[LearningObservation]:
        """Extract learning observations from a result."""
        observations = []

        if "agents" in result:
            observations.append(LearningObservation(
                observation_id=f"obs_agents_{len(self._observations)}",
                domain=LearningDomain.AGENT_COLLABORATION,
                description=f"Agent collaboration observed with {result.get('count', 0)} agents",
                source_agents=list(result["agents"]) if isinstance(result["agents"], list) else [],
                impact=0.5,
            ))

        if "decision" in result:
            observations.append(LearningObservation(
                observation_id=f"obs_decision_{len(self._observations)}",
                domain=LearningDomain.DECISION_QUALITY,
                description=f"Decision made: {result.get('decision', 'unknown')}",
                source_agents=[],
                impact=0.6,
            ))

        if "phases" in result:
            observations.append(LearningObservation(
                observation_id=f"obs_process_{len(self._observations)}",
                domain=LearningDomain.PROCESS_EFFICIENCY,
                description=f"Process completed with {len(result['phases'])} phases",
                source_agents=[],
                impact=0.4,
            ))

        return observations

    def _generate_insights(self) -> List[OrganizationInsight]:
        """Generate insights from accumulated observations."""
        insights = []

        # Check for collaboration patterns
        collab_obs = [o for o in self._observations if o.domain == LearningDomain.AGENT_COLLABORATION]
        if len(collab_obs) >= 3:
            insights.append(OrganizationInsight(
                insight_id=f"insight_collab_{len(self._insights)}",
                domain=LearningDomain.AGENT_COLLABORATION,
                finding="Multiple agent collaborations observed - pattern analysis recommended",
                confidence=0.7,
                supporting_observations=len(collab_obs),
                action_required=False,
                recommendation="Continue monitoring collaboration effectiveness",
            ))

        # Check for decision quality
        decision_obs = [o for o in self._observations if o.domain == LearningDomain.DECISION_QUALITY]
        if decision_obs:
            avg_impact = sum(o.impact for o in decision_obs) / len(decision_obs)
            if avg_impact > 0.7:
                insights.append(OrganizationInsight(
                    insight_id=f"insight_decision_{len(self._insights)}",
                    domain=LearningDomain.DECISION_QUALITY,
                    finding="Decision quality is high - maintain current processes",
                    confidence=0.8,
                    supporting_observations=len(decision_obs),
                    action_required=False,
                    recommendation="Current decision framework is effective",
                ))

        return insights

    def _track_metrics(self, result: Dict[str, Any]):
        """Track organizational metrics."""
        if "count" in result:
            self._metrics["agent_count"].append(result["count"])
        if "phases" in result:
            self._metrics["phases_executed"].append(len(result["phases"]))

    def _get_key_findings(self) -> List[str]:
        """Get key findings from organizational learning."""
        findings = []
        insights = self._insights[-5:] if self._insights else []
        for i in insights:
            findings.append(i.finding)
        if not findings:
            findings.append("Organization is building its learning base")
        return findings

    def _calculate_organization_score(self) -> float:
        """Calculate overall organization effectiveness score."""
        if not self._observations:
            return 0.5

        avg_impact = sum(o.impact for o in self._observations) / len(self._observations)
        insight_rate = len(self._insights) / max(len(self._observations), 1)
        improvement_rate = len(self._improvements) / max(len(self._observations), 1)

        return (avg_impact * 0.4 + insight_rate * 0.3 + improvement_rate * 0.3)

    def _determine_trend(self) -> str:
        """Determine organizational trend."""
        if len(self._observations) < 3:
            return "BUILDING"
        recent = self._observations[-3:]
        older = self._observations[:-3] if len(self._observations) > 3 else self._observations
        recent_avg = sum(o.impact for o in recent) / len(recent)
        older_avg = sum(o.impact for o in older) / len(older) if older else recent_avg

        if recent_avg > older_avg * 1.05:
            return "IMPROVING"
        elif recent_avg < older_avg * 0.95:
            return "DECLINING"
        return "STABLE"

    def _generate_recommendations(self) -> List[str]:
        """Generate organizational improvement recommendations."""
        recs = []
        insights_with_action = [i for i in self._insights if i.action_required]
        for i in insights_with_action[-3:]:
            recs.append(i.recommendation)
        if not recs:
            recs.append("Continue current organizational practices")
        return recs

    def _generate_next_actions(self) -> List[str]:
        """Generate next action items for the organization."""
        actions = []
        if len(self._observations) < 5:
            actions.append("Gather more organizational data")
        if len(self._insights) < 3:
            actions.append("Generate insights from existing observations")
        if self._calculate_organization_score() < 0.5:
            actions.append("Focus on improving organizational effectiveness")
        if not actions:
            actions.append("Review and optimize current processes")
        return actions
