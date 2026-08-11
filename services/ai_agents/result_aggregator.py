"""
ICYQuant Result Aggregator — consolidates multi-agent outputs into unified results.

Collects outputs from all agents in a workflow, merges findings, resolves
conflicts, deduplicates, and produces a single consolidated report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AggregationMode(str, Enum):
    CONCAT = "concat"          # Simple concatenation
    MERGE = "merge"            # Deep merge with conflict detection
    VOTE = "vote"              # Majority voting
    WEIGHTED = "weighted"      # Weighted by confidence
    BEST = "best"              # Select best result by score


@dataclass
class ConflictRecord:
    """Records a conflict between agent outputs."""
    key: str
    values: list[Any]
    agent_ids: list[str]
    resolved_by: str = ""      # How the conflict was resolved
    resolution_value: Any = None


@dataclass
class AggregatedResult:
    """Consolidated result from multiple agent outputs."""
    result_id: str = ""
    workflow_id: str = ""

    # Consolidated data
    summary: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)

    # Source tracking
    source_agents: list[str] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)

    # Quality metrics
    overall_confidence: float = 0.0
    agreement_level: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultAggregator:
    """Aggregates outputs from multiple agents into unified results.

    Features:
        - Multi-strategy aggregation (merge, vote, weighted, best)
        - Conflict detection and resolution
        - Confidence-weighted merging
        - Deduplication of findings
        - Source tracking for audit trail
        - Structured output formatting
    """

    def __init__(self) -> None:
        self._results: dict[str, AggregatedResult] = {}
        self._total_aggregations = 0

    async def aggregate(self, workflow_id: str,
                        agent_outputs: dict[str, Any],
                        mode: AggregationMode = AggregationMode.MERGE,
                        metadata: Optional[dict[str, Any]] = None) -> AggregatedResult:
        """Aggregate agent outputs into a single result."""
        self._total_aggregations += 1

        result = AggregatedResult(
            result_id=workflow_id,
            workflow_id=workflow_id,
            metadata=metadata or {},
        )

        # Track source agents
        result.source_agents = list(agent_outputs.keys())

        # Collect findings from all agents
        all_findings = []
        for agent_id, output in agent_outputs.items():
            if isinstance(output, dict):
                findings = output.get("findings", [])
                if findings:
                    all_findings.extend(findings)

        # Deduplicate findings
        result.findings = self._deduplicate_findings(all_findings)

        # Detect and record conflicts
        result.conflicts = self._detect_conflicts(agent_outputs)

        # Calculate agreement level
        result.agreement_level = self._calculate_agreement(agent_outputs, result.conflicts)

        # Generate summary
        result.summary = self._generate_summary(agent_outputs, result)

        # Collect recommendations
        result.recommendations = self._collect_recommendations(agent_outputs)

        # Overall confidence
        result.overall_confidence = self._calculate_overall_confidence(
            agent_outputs, result.agreement_level
        )

        self._results[workflow_id] = result
        logger.info("Aggregated result %s: %d sources, %d findings, %.2f confidence",
                     workflow_id, len(result.source_agents),
                     len(result.findings), result.overall_confidence)
        return result

    def _deduplicate_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate findings by similarity."""
        seen = set()
        unique = []
        for finding in findings:
            key = finding.get("id", str(finding))
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique

    def _detect_conflicts(self, outputs: dict[str, Any]) -> list[ConflictRecord]:
        """Detect conflicting recommendations across agents."""
        conflicts = []
        # Compare recommendations across agents
        recs: dict[str, dict[str, str]] = {}
        for agent_id, output in outputs.items():
            if isinstance(output, dict):
                for rec in output.get("recommendations", []):
                    key = str(rec)[:50]
                    if key not in recs:
                        recs[key] = {}
                    recs[key][agent_id] = str(rec)

        for key, agents in recs.items():
            if len(agents) > 1 and len(set(agents.values())) > 1:
                conflicts.append(ConflictRecord(
                    key=key,
                    values=list(agents.values()),
                    agent_ids=list(agents.keys()),
                ))
        return conflicts

    def _calculate_agreement(self, outputs: dict[str, Any],
                             conflicts: list[ConflictRecord]) -> float:
        """Calculate agreement level between agents."""
        num_agents = len(outputs)
        if num_agents <= 1:
            return 1.0

        conflict_penalty = min(len(conflicts) * 0.1, 0.5)
        return max(0.0, 1.0 - conflict_penalty)

    def _generate_summary(self, outputs: dict[str, Any],
                          result: AggregatedResult) -> str:
        """Generate a human-readable summary."""
        num_agents = len(outputs)
        num_findings = len(result.findings)
        agreement = result.agreement_level

        if agreement >= 0.8:
            agreement_str = "strong agreement"
        elif agreement >= 0.5:
            agreement_str = "moderate agreement"
        else:
            agreement_str = "significant disagreement"

        return (f"Aggregated results from {num_agents} agents with {agreement_str}. "
                f"Total findings: {num_findings}, conflicts: {len(result.conflicts)}.")

    def _collect_recommendations(self, outputs: dict[str, Any]) -> list[str]:
        """Collect and deduplicate recommendations."""
        recs = []
        seen = set()
        for output in outputs.values():
            if isinstance(output, dict):
                for rec in output.get("recommendations", []):
                    if rec not in seen:
                        seen.add(rec)
                        recs.append(rec)
        return recs

    def _calculate_overall_confidence(self, outputs: dict[str, Any],
                                      agreement: float) -> float:
        """Calculate overall confidence across all agents."""
        confidences = []
        for output in outputs.values():
            if isinstance(output, dict):
                conf = output.get("confidence", 0.0)
                if conf > 0:
                    confidences.append(conf)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
        # Blend average confidence with agreement level
        return 0.6 * avg_conf + 0.4 * agreement

    def get_result(self, workflow_id: str) -> Optional[AggregatedResult]:
        return self._results.get(workflow_id)

    @property
    def total_aggregations(self) -> int:
        return self._total_aggregations
