"""
Stress Test Runner — Orchestrates the execution of batch stress tests with concurrency control.

Manages parallel execution of multiple stress scenarios, collects results,
and provides progress tracking and cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class StressTestRunConfig:
    """Configuration for a stress test run."""
    batch_size: int = 10
    timeout_per_scenario_seconds: float = 60.0
    max_retries_per_scenario: int = 2
    collect_diagnostics: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestRunResult:
    """Aggregate result from a stress test run."""
    run_id: str
    total_scenarios: int
    completed: int
    failed: int
    cancelled: int
    total_time_ms: float
    worst_loss_pct: float
    worst_scenario: str
    risk_distribution: dict[str, int]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    diagnostics: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class StressTestRunner:
    """
    Orchestrates batch execution of stress tests with concurrency control.

    Features:
    - Parallel scenario execution with configurable batch size
    - Timeout and retry per scenario
    - Progress tracking and cancellation
    - Diagnostics collection

    Usage::

        runner = StressTestRunner(engine, config=StressTestRunConfig())
        result = await runner.run(portfolio_data, scenario_ids=["2008", "covid"])
    """

    def __init__(
        self,
        stress_engine: Any = None,
        config: Optional[StressTestRunConfig] = None,
    ) -> None:
        self._engine = stress_engine
        self._config = config or StressTestRunConfig()
        self._cancelled = False
        self._on_progress: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    @property
    def config(self) -> StressTestRunConfig:
        return self._config

    def set_progress_callback(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback

    def set_complete_callback(self, callback: Callable) -> None:
        """Set callback for completion."""
        self._on_complete = callback

    async def run(
        self,
        portfolio_data: dict[str, Any],
        scenario_ids: Optional[list[str]] = None,
    ) -> StressTestRunResult:
        """
        Run batch stress tests.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio snapshot data.
        scenario_ids : list[str], optional
            Specific scenarios to run.

        Returns
        -------
        StressTestRunResult
            Aggregate results.
        """
        import time
        import uuid

        run_id = str(uuid.uuid4())
        t_start = time.perf_counter()
        self._cancelled = False

        # Get scenarios
        if self._engine:
            if scenario_ids:
                scenarios = [
                    self._engine.get_scenario(sid)
                    for sid in scenario_ids
                    if self._engine.get_scenario(sid)
                ]
            else:
                scenarios = self._engine.list_scenarios()
        else:
            scenarios = []

        total = len(scenarios)
        if total == 0:
            return StressTestRunResult(
                run_id=run_id,
                total_scenarios=0,
                completed=0,
                failed=0,
                cancelled=0,
                total_time_ms=0,
                worst_loss_pct=0,
                worst_scenario="",
                risk_distribution={},
            )

        # Process in batches
        results: list[dict] = []
        completed = 0
        failed = 0
        cancelled = 0
        worst_loss_pct = 0.0
        worst_scenario = ""
        risk_distribution: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for batch_start in range(0, total, self._config.batch_size):
            if self._cancelled:
                cancelled += total - completed - failed
                break

            batch = scenarios[batch_start:batch_start + self._config.batch_size]

            tasks = []
            for scenario in batch:
                if self._cancelled:
                    cancelled += 1
                    continue
                tasks.append(
                    self._run_scenario_with_retry(portfolio_data, scenario)
                )

            if not tasks:
                continue

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, res in enumerate(batch_results):
                if isinstance(res, Exception):
                    failed += 1
                    results.append({
                        "scenario_id": batch[i].scenario_id if hasattr(batch[i], 'scenario_id') else "unknown",
                        "error": str(res),
                    })
                elif res is None:
                    cancelled += 1
                else:
                    completed += 1
                    results.append(res)
                    loss = abs(res.get("loss_percentage", 0))
                    if loss > worst_loss_pct:
                        worst_loss_pct = loss
                        worst_scenario = res.get("scenario_name", "")
                    rl = res.get("risk_level", "low")
                    if rl in risk_distribution:
                        risk_distribution[rl] += 1

            # Progress callback
            progress = (completed + failed + cancelled) / total * 100
            if self._on_progress:
                try:
                    self._on_progress(progress, completed, failed, cancelled)
                except Exception:
                    pass

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        result = StressTestRunResult(
            run_id=run_id,
            total_scenarios=total,
            completed=completed,
            failed=failed,
            cancelled=cancelled,
            total_time_ms=elapsed_ms,
            worst_loss_pct=worst_loss_pct,
            worst_scenario=worst_scenario,
            risk_distribution=risk_distribution,
            completed_at=datetime.now(timezone.utc),
            diagnostics=await self._collect_diagnostics() if self._config.collect_diagnostics else None,
        )

        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

        return result

    def cancel(self) -> None:
        """Cancel the current run."""
        self._cancelled = True
        logger.warning("StressTestRunner: run cancelled.")

    async def _run_scenario_with_retry(
        self,
        portfolio_data: dict[str, Any],
        scenario: Any,
    ) -> Optional[dict]:
        """Run a single scenario with retry logic."""
        if self._cancelled:
            return None

        for attempt in range(self._config.max_retries_per_scenario + 1):
            try:
                if self._engine:
                    result = await asyncio.wait_for(
                        self._engine._run_single_scenario(
                            scenario,
                            portfolio_data.get("positions", []),
                            portfolio_data.get("total_value", 0.0),
                        ),
                        timeout=self._config.timeout_per_scenario_seconds,
                    )
                    return {
                        "scenario_id": result.scenario_id,
                        "scenario_name": result.scenario_name,
                        "loss_percentage": result.loss_percentage,
                        "risk_level": result.risk_level,
                        "breached_limits": result.breached_limits,
                    }
            except asyncio.TimeoutError:
                logger.warning(f"Scenario '{scenario.scenario_id}' timed out (attempt {attempt + 1}).")
            except Exception as e:
                logger.warning(f"Scenario '{scenario.scenario_id}' failed (attempt {attempt + 1}): {e}")
                if attempt == self._config.max_retries_per_scenario:
                    raise

        return None

    async def _collect_diagnostics(self) -> dict[str, Any]:
        """Collect run diagnostics."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "batch_size": self._config.batch_size,
                "timeout": self._config.timeout_per_scenario_seconds,
                "max_retries": self._config.max_retries_per_scenario,
            },
        }
