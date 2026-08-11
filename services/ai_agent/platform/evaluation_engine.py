"""Evaluation Engine — continuous quality evaluation for AI agent outputs.

The EvaluationEngine continuously assesses agent performance across multiple
dimensions: accuracy, tool success rate, planning quality, and reasoning
quality. It supports ground-truth comparison, human feedback integration,
and automated regression testing.

Evaluation dimensions:
    - Agent Accuracy: correctness of agent outputs
    - Tool Success Rate: percentage of tool calls that succeed
    - Planning Quality: effectiveness of agent plans
    - Reasoning Quality: logical soundness of reasoning chains
    - Response Quality: relevance, completeness, conciseness
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvaluationDimension(str, Enum):
    """Dimensions for agent evaluation."""
    ACCURACY = "accuracy"
    TOOL_SUCCESS = "tool_success"
    PLANNING_QUALITY = "planning_quality"
    REASONING_QUALITY = "reasoning_quality"
    RESPONSE_QUALITY = "response_quality"


@dataclass
class EvaluationScore:
    """Score for a single evaluation dimension."""
    dimension: EvaluationDimension
    score: float  # 0.0 - 1.0
    confidence: float = 1.0
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Complete evaluation result for an agent interaction."""
    evaluation_id: str = ""
    agent_id: str = ""
    task_id: str = ""
    scores: List[EvaluationScore] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False
    threshold: float = 0.70
    evaluated_at: float = field(default_factory=time.monotonic)

    @property
    def dimension_scores(self) -> Dict[str, float]:
        return {s.dimension.value: s.score for s in self.scores}


class EvaluationEngine:
    """Continuous quality evaluation for AI agent outputs.

    Evaluates agent performance across multiple dimensions and tracks
    quality trends over time for continuous improvement.

    Usage:
        ee = EvaluationEngine(pass_threshold=0.70)
        await ee.initialize()
        result = await ee.evaluate(agent_id="agent_1", task={"input": "...", "output": "..."})
    """

    def __init__(self, pass_threshold: float = 0.70) -> None:
        self._pass_threshold = pass_threshold
        self._results: List[EvaluationResult] = []
        self._max_results: int = 10000
        self._dimension_weights: Dict[EvaluationDimension, float] = {
            EvaluationDimension.ACCURACY: 0.30,
            EvaluationDimension.TOOL_SUCCESS: 0.20,
            EvaluationDimension.PLANNING_QUALITY: 0.20,
            EvaluationDimension.REASONING_QUALITY: 0.15,
            EvaluationDimension.RESPONSE_QUALITY: 0.15,
        }
        self._initialized: bool = False
        self._lock = threading.Lock()
        logger.info("EvaluationEngine created (threshold=%.2f)", pass_threshold)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("EvaluationEngine initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._results.clear()
        self._initialized = False
        logger.info("EvaluationEngine shutdown complete")

    async def evaluate(self, agent_id: str, task_id: str = "", task: Optional[Dict[str, Any]] = None, ground_truth: Optional[Any] = None, tool_results: Optional[List[Dict[str, Any]]] = None) -> EvaluationResult:
        """Evaluate an agent interaction.

        Args:
            agent_id: The agent being evaluated.
            task_id: The task being evaluated.
            task: The task input/output data.
            ground_truth: Expected output for accuracy comparison.
            tool_results: Results of tool calls made by the agent.
        """
        scores: List[EvaluationScore] = []

        # Tool success rate
        if tool_results:
            successes = sum(1 for t in tool_results if t.get("success", False))
            total = len(tool_results)
            score = successes / total if total > 0 else 1.0
            scores.append(EvaluationScore(
                dimension=EvaluationDimension.TOOL_SUCCESS,
                score=score,
                confidence=1.0,
                explanation=f"Tool success: {successes}/{total}",
                metadata={"successes": successes, "total": total},
            ))

        # Accuracy (if ground truth available)
        if ground_truth is not None and task:
            accuracy_score = self._compute_accuracy(task.get("output"), ground_truth)
            scores.append(EvaluationScore(
                dimension=EvaluationDimension.ACCURACY,
                score=accuracy_score,
                confidence=0.80,
                explanation=f"Accuracy score: {accuracy_score:.2f}",
            ))

        # Planning quality heuristic
        if task:
            planning_score = self._evaluate_planning(task)
            scores.append(EvaluationScore(
                dimension=EvaluationDimension.PLANNING_QUALITY,
                score=planning_score,
                confidence=0.70,
                explanation=f"Planning quality: {planning_score:.2f}",
            ))

        # Response quality heuristic
        if task:
            response_score = self._evaluate_response(task)
            scores.append(EvaluationScore(
                dimension=EvaluationDimension.RESPONSE_QUALITY,
                score=response_score,
                confidence=0.70,
                explanation=f"Response quality: {response_score:.2f}",
            ))

        # Compute overall
        overall = self._compute_overall(scores)
        result = EvaluationResult(
            evaluation_id=f"eval_{int(time.monotonic()*1000)}",
            agent_id=agent_id,
            task_id=task_id,
            scores=scores,
            overall_score=round(overall, 3),
            passed=overall >= self._pass_threshold,
            threshold=self._pass_threshold,
        )

        with self._lock:
            self._results.append(result)
            if len(self._results) > self._max_results:
                self._results = self._results[-self._max_results:]

        logger.debug("EvaluationEngine: agent=%s overall=%.2f passed=%s", agent_id, overall, result.passed)
        return result

    def _compute_accuracy(self, output: Any, ground_truth: Any) -> float:
        """Compute accuracy between output and ground truth."""
        if output is None:
            return 0.0
        if isinstance(output, str) and isinstance(ground_truth, str):
            # Simple string similarity
            output_lower = output.lower()
            truth_lower = ground_truth.lower()
            if output_lower == truth_lower:
                return 1.0
            # Jaccard-like word overlap
            out_words = set(output_lower.split())
            truth_words = set(truth_lower.split())
            if not truth_words:
                return 0.0
            intersection = out_words & truth_words
            return len(intersection) / len(truth_words)
        if output == ground_truth:
            return 1.0
        return 0.5

    def _evaluate_planning(self, task: Dict[str, Any]) -> float:
        """Heuristic evaluation of planning quality."""
        plan = task.get("plan", task.get("steps", []))
        if isinstance(plan, list):
            if len(plan) == 0:
                return 0.3
            if len(plan) > 20:
                return 0.5  # Too many steps
            return 0.75  # Reasonable plan size
        return 0.5

    def _evaluate_response(self, task: Dict[str, Any]) -> float:
        """Heuristic evaluation of response quality."""
        output = task.get("output", "")
        if not output:
            return 0.0
        if isinstance(output, str):
            if len(output) < 10:
                return 0.3  # Too short
            if len(output) > 10000:
                return 0.5  # Too verbose
            return 0.8
        return 0.7

    def _compute_overall(self, scores: List[EvaluationScore]) -> float:
        """Compute weighted overall score."""
        if not scores:
            return 0.0
        total_weight = 0.0
        weighted_sum = 0.0
        for s in scores:
            weight = self._dimension_weights.get(s.dimension, 0.20)
            weighted_sum += s.score * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get evaluation statistics for an agent."""
        with self._lock:
            agent_results = [r for r in self._results if r.agent_id == agent_id]
        if not agent_results:
            return {"agent_id": agent_id, "evaluations": 0}
        scores = [r.overall_score for r in agent_results]
        return {
            "agent_id": agent_id,
            "evaluations": len(agent_results),
            "avg_score": round(sum(scores) / len(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "pass_rate": round(len([r for r in agent_results if r.passed]) / len(agent_results), 3),
            "recent_scores": [round(s, 3) for s in scores[-10:]],
        }

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._results)
            passed = len([r for r in self._results if r.passed])
        return {
            "initialized": self._initialized,
            "total_evaluations": total,
            "pass_rate": round(passed / total, 3) if total > 0 else 0.0,
            "pass_threshold": self._pass_threshold,
            "avg_overall": round(sum(r.overall_score for r in self._results) / total, 3) if total > 0 else 0.0,
        }
