"""Benchmark Engine — standardized benchmarking for AI agent performance.

The BenchmarkEngine provides a framework for running standardized benchmarks
against AI agents to measure and compare performance over time. It supports
predefined benchmark suites, custom test cases, and comparative analysis.

Benchmark suites:
    - Reasoning benchmarks
    - Tool-use benchmarks
    - Planning benchmarks
    - Multi-agent coordination benchmarks
    - Financial domain-specific benchmarks
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkStatus(str, Enum):
    """Status of a benchmark run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BenchmarkCase:
    """A single benchmark test case."""
    case_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    category: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[Any] = None
    evaluation_fn: Optional[Callable] = None
    timeout_sec: float = 60.0
    weight: float = 1.0


@dataclass
class BenchmarkResult:
    """Result of a single benchmark case execution."""
    case_id: str = ""
    case_name: str = ""
    score: float = 0.0
    passed: bool = False
    latency_ms: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkRun:
    """Complete benchmark run with all case results."""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    suite_name: str = ""
    agent_id: str = ""
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    results: List[BenchmarkResult] = field(default_factory=list)
    overall_score: float = 0.0
    pass_rate: float = 0.0
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None
    total_latency_ms: float = 0.0


class BenchmarkEngine:
    """Standardized benchmarking for AI agent performance.

    Runs benchmark suites against agents to measure and compare performance,
    tracking improvements and regressions over time.

    Usage:
        be = BenchmarkEngine()
        await be.initialize()
        be.register_suite("reasoning", [BenchmarkCase(name="logic_1", ...)])
        run = await be.run_benchmark(agent_id="agent_1", suite_name="reasoning", execute_fn=my_agent_fn)
    """

    def __init__(self) -> None:
        self._suites: Dict[str, List[BenchmarkCase]] = {}
        self._runs: List[BenchmarkRun] = []
        self._max_runs: int = 500
        self._initialized: bool = False
        logger.info("BenchmarkEngine created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("BenchmarkEngine initialized")

    async def shutdown(self) -> None:
        self._suites.clear()
        self._runs.clear()
        self._initialized = False
        logger.info("BenchmarkEngine shutdown complete")

    def register_suite(self, suite_name: str, cases: List[BenchmarkCase]) -> None:
        """Register a benchmark suite with test cases."""
        self._suites[suite_name] = cases
        logger.info("BenchmarkEngine: registered suite '%s' (%d cases)", suite_name, len(cases))

    def add_case(self, suite_name: str, case: BenchmarkCase) -> None:
        """Add a case to an existing suite."""
        self._suites.setdefault(suite_name, []).append(case)

    def get_suite(self, suite_name: str) -> Optional[List[BenchmarkCase]]:
        """Get all cases in a benchmark suite."""
        return self._suites.get(suite_name)

    def list_suites(self) -> List[str]:
        """List all registered benchmark suites."""
        return sorted(self._suites.keys())

    async def run_benchmark(self, agent_id: str, suite_name: str, execute_fn: Callable) -> BenchmarkRun:
        """Run a full benchmark suite against an agent.

        Args:
            agent_id: The agent to benchmark.
            suite_name: The benchmark suite to run.
            execute_fn: Async function that executes the agent with case input.
        """
        cases = self._suites.get(suite_name, [])
        if not cases:
            raise ValueError(f"Benchmark suite '{suite_name}' not found")

        run = BenchmarkRun(suite_name=suite_name, agent_id=agent_id)
        run.status = BenchmarkStatus.RUNNING

        for case in cases:
            try:
                start = time.monotonic()
                output = await execute_fn(agent_id, case.input_data)
                elapsed = (time.monotonic() - start) * 1000

                if case.evaluation_fn:
                    score = case.evaluation_fn(output, case.expected_output)
                elif case.expected_output is not None:
                    score = 1.0 if output == case.expected_output else 0.0
                else:
                    score = 0.5  # No ground truth

                result = BenchmarkResult(
                    case_id=case.case_id,
                    case_name=case.name,
                    score=score,
                    passed=score >= 0.70,
                    latency_ms=round(elapsed, 2),
                    details={"output": str(output)[:500]},
                )
            except Exception as e:
                result = BenchmarkResult(
                    case_id=case.case_id,
                    case_name=case.name,
                    score=0.0,
                    passed=False,
                    error=str(e),
                )

            run.results.append(result)

        # Compute aggregate scores
        total_weight = sum(c.weight for c in cases)
        if total_weight > 0:
            weighted_scores = []
            for case, result in zip(cases, run.results):
                weighted_scores.append(result.score * case.weight)
            run.overall_score = round(sum(weighted_scores) / total_weight, 3)

        passed = len([r for r in run.results if r.passed])
        run.pass_rate = round(passed / len(run.results), 3) if run.results else 0.0
        run.total_latency_ms = round(sum(r.latency_ms for r in run.results), 2)
        run.completed_at = time.monotonic()
        run.status = BenchmarkStatus.COMPLETED

        self._runs.append(run)
        if len(self._runs) > self._max_runs:
            self._runs = self._runs[-self._max_runs:]

        logger.info("BenchmarkEngine: suite '%s' completed for %s (score=%.2f, pass_rate=%.0f%%)", suite_name, agent_id, run.overall_score, run.pass_rate * 100)
        return run

    def get_agent_history(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get benchmark history for an agent."""
        runs = [r for r in self._runs if r.agent_id == agent_id]
        return sorted([
            {
                "run_id": r.run_id,
                "suite": r.suite_name,
                "overall_score": r.overall_score,
                "pass_rate": r.pass_rate,
                "cases": len(r.results),
                "latency_ms": r.total_latency_ms,
                "completed_at": r.completed_at,
            }
            for r in runs
        ], key=lambda x: x["completed_at"] or 0, reverse=True)[:limit]

    def compare_runs(self, run_id_1: str, run_id_2: str) -> Optional[Dict[str, Any]]:
        """Compare two benchmark runs."""
        run1 = next((r for r in self._runs if r.run_id == run_id_1), None)
        run2 = next((r for r in self._runs if r.run_id == run_id_2), None)
        if not run1 or not run2:
            return None
        return {
            "run_1": {"score": run1.overall_score, "pass_rate": run1.pass_rate, "latency_ms": run1.total_latency_ms},
            "run_2": {"score": run2.overall_score, "pass_rate": run2.pass_rate, "latency_ms": run2.total_latency_ms},
            "delta_score": round(run2.overall_score - run1.overall_score, 3),
            "delta_pass_rate": round(run2.pass_rate - run1.pass_rate, 3),
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "registered_suites": len(self._suites),
            "total_cases": sum(len(cases) for cases in self._suites.values()),
            "total_runs": len(self._runs),
            "suites": sorted(self._suites.keys()),
        }
