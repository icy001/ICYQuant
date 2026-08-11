"""
Optimization Memory — persistent storage of optimization runs,
their parameters, results, and convergence history.

Stores complete optimization records for:
    - Portfolio optimization runs with full parameter snapshots
    - Convergence history tracking for algorithm improvement
    - Comparative analysis between optimization approaches
    - Aggregate statistics for optimizer calibration
    - Audit trail for risk governance and compliance

Used by:
    - Risk Optimizer for historical pattern recognition
    - Execution Optimizer for strategy selection
    - Pre-Trade Optimizer for parameter calibration
    - Execution Learning for optimization context
    - Audit / Compliance for decision traceability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OptimizerType(Enum):
    """Classification of optimization algorithms."""

    MEAN_VARIANCE = "mean_variance"
    RISK_PARITY = "risk_parity"
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    BLACK_LITTERMAN = "black_litterman"
    ROBUST = "robust"
    CARDINAL = "cardinal"
    GRADIENT = "gradient"
    BAYESIAN = "bayesian"


class OptimizationObjective(Enum):
    """Classification of optimization objectives."""

    MINIMIZE_VAR = "minimize_var"
    MINIMIZE_ES = "minimize_es"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_DIVERSIFICATION = "maximize_diversification"
    MINIMIZE_TRANSACTION_COST = "minimize_transaction_cost"


@dataclass
class OptimizationRun:
    """
    A complete optimization run record.

    Captures the full context of an optimization run including:
        - Which portfolio was optimized
        - What strategy and optimizer were used
        - Input and output positions
        - Objective function value and convergence status
        - Performance metrics (iterations, duration)
        - Any warnings or issues encountered
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    strategy: str = ""
    optimizer_type: OptimizerType = OptimizerType.MEAN_VARIANCE
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
    parameters: dict[str, Any] = field(default_factory=dict)
    input_positions: dict[str, float] = field(default_factory=dict)
    output_positions: dict[str, float] = field(default_factory=dict)
    objective_value: float = 0.0
    convergence_achieved: bool = False
    iterations: int = 0
    duration_ms: float = 0.0
    success: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConvergencePoint:
    """
    A single point in the convergence history of an optimization run.

    Captures the state of the optimizer at a specific iteration,
    including the objective value, step size, gradient norm, and
    elapsed time for convergence analysis.
    """

    iteration: int = 0
    objective_value: float = 0.0
    step_size: float = 0.0
    gradient_norm: float = 0.0
    elapsed_ms: float = 0.0


@dataclass
class OptimizationMemoryStats:
    """
    Aggregate statistics from optimization memory.

    Provides a summary view of all optimization runs tracked in memory,
    useful for dashboards, optimizer calibration, and strategy selection.
    """

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_iterations: float = 0.0
    avg_duration_ms: float = 0.0
    best_sharpe: float = 0.0
    best_var_reduction: float = 0.0
    by_optimizer: dict[str, int] = field(default_factory=dict)
    by_strategy: dict[str, int] = field(default_factory=dict)
    convergence_rate_pct: float = 0.0


class OptimizationMemory:
    """
    Persistent storage for optimization runs and convergence history.

    Architecture:
        - In-memory storage with configurable capacity
        - Append-only log for optimization runs and convergence data
        - Query interface filtered by strategy, optimizer, and performance
        - Aggregate statistics for monitoring and calibration

    Storage Tiers:
        1. Optimization Runs — full records of every optimization executed
        2. Convergence History — per-run iteration-level convergence data
        3. Comparative Analysis — run-to-run comparison for improvement tracking
        4. Aggregate Stats — summary metrics for dashboard and reporting

    Usage:
        memory = OptimizationMemory(max_runs=2000)
        run_id = await memory.store_run(run)
        await memory.store_convergence(run_id, history)
        best = await memory.get_best_runs(strategy="momentum", top_n=10)
        stats = await memory.get_stats()
    """

    def __init__(self, max_runs: int = 2000) -> None:
        self._max_runs = max_runs
        self._runs: list[OptimizationRun] = []
        self._convergence: dict[str, list[ConvergencePoint]] = {}
        self._total_runs_stored: int = 0

    async def store_run(self, run: OptimizationRun) -> str:
        """
        Store an optimization run record.

        Appends the run to memory and trims old entries when the
        maximum capacity is reached, preserving the most recent half
        of the entries.

        Args:
            run: The optimization run to store.

        Returns:
            The unique identifier of the stored run.
        """
        self._runs.append(run)
        self._total_runs_stored += 1

        if len(self._runs) > self._max_runs:
            removed = self._runs[:-self._max_runs // 2]
            self._runs = self._runs[-self._max_runs // 2:]

            for r in removed:
                self._convergence.pop(r.id, None)

        logger.info(
            "Stored optimization run %s (optimizer=%s, objective=%s, "
            "success=%s, iterations=%d, duration=%.2fms)",
            run.id,
            run.optimizer_type.value,
            run.objective.value,
            run.success,
            run.iterations,
            run.duration_ms,
        )
        return run.id

    async def store_convergence(
        self, run_id: str, history: list[ConvergencePoint]
    ) -> str:
        """
        Store convergence history for a specific optimization run.

        Associates convergence iteration data with an existing run
        identifier. If the run does not exist, the convergence data
        is still stored but logged as an orphaned entry.

        Args:
            run_id: The unique identifier of the optimization run.
            history: A list of ConvergencePoint representing the
                iteration-by-iteration trajectory of the optimizer.

        Returns:
            The run_id for which convergence was stored.
        """
        self._convergence[run_id] = history

        run_exists = any(r.id == run_id for r in self._runs)
        if not run_exists:
            logger.warning(
                "Stored convergence for unknown run %s (run may have been trimmed)",
                run_id,
            )

        logger.info(
            "Stored convergence history for run %s (%d points)",
            run_id,
            len(history),
        )
        return run_id

    async def get_run_history(
        self,
        strategy: str = "",
        optimizer: str = "",
        limit: int = 100,
    ) -> list[OptimizationRun]:
        """
        Retrieve optimization run history with optional filters.

        Args:
            strategy: Filter by strategy name (empty = all).
            optimizer: Filter by optimizer type name (empty = all).
            limit: Maximum number of records to return.

        Returns:
            A list of optimization run records, most recent first.
        """
        results = self._runs

        if strategy:
            results = [r for r in results if r.strategy == strategy]
        if optimizer:
            results = [
                r for r in results if r.optimizer_type.value == optimizer
            ]

        return list(reversed(results[-limit:]))

    async def get_best_runs(
        self, strategy: str, top_n: int = 10
    ) -> list[OptimizationRun]:
        """
        Retrieve the best optimization runs for a given strategy.

        Returns the top N runs sorted by objective value (descending
        for maximization objectives, ascending for minimization).

        Args:
            strategy: The strategy name to filter by.
            top_n: Maximum number of best runs to return.

        Returns:
            A list of the best optimization runs for the strategy,
            ordered by objective value quality.
        """
        strategy_runs = [r for r in self._runs if r.strategy == strategy]

        if not strategy_runs:
            return []

        maximization_objectives = {
            OptimizationObjective.MAXIMIZE_SHARPE,
            OptimizationObjective.MAXIMIZE_DIVERSIFICATION,
        }

        first_run = strategy_runs[0]
        is_maximization = first_run.objective in maximization_objectives

        if is_maximization:
            sorted_runs = sorted(
                strategy_runs,
                key=lambda r: r.objective_value,
                reverse=True,
            )
        else:
            sorted_runs = sorted(
                strategy_runs,
                key=lambda r: r.objective_value,
            )

        return sorted_runs[:top_n]

    async def get_convergence_history(
        self, run_id: str
    ) -> list[ConvergencePoint]:
        """
        Retrieve the convergence history for a specific optimization run.

        Args:
            run_id: The unique identifier of the optimization run.

        Returns:
            A list of ConvergencePoint representing the iteration
            trajectory, or an empty list if no convergence data exists.
        """
        return self._convergence.get(run_id, [])

    async def compare_runs(
        self, run_id_1: str, run_id_2: str
    ) -> dict[str, Any]:
        """
        Compare two optimization runs in detail.

        Produces a side-by-side comparison of two runs including
        parameters, results, convergence behavior, and performance
        metrics to aid optimizer selection and calibration.

        Args:
            run_id_1: The unique identifier of the first optimization run.
            run_id_2: The unique identifier of the second optimization run.

        Returns:
            A dictionary containing comparison metrics including
            parameter differences, result deltas, convergence analysis,
            and a summary of which run performed better.
        """
        run_1 = self._find_run(run_id_1)
        run_2 = self._find_run(run_id_2)

        if run_1 is None and run_2 is None:
            return {"status": "not_found", "message": "Both runs not found"}
        if run_1 is None:
            return {"status": "not_found", "message": f"Run {run_id_1} not found"}
        if run_2 is None:
            return {"status": "not_found", "message": f"Run {run_id_2} not found"}

        conv_1 = self._convergence.get(run_id_1, [])
        conv_2 = self._convergence.get(run_id_2, [])

        param_diff = self._diff_dicts(run_1.parameters, run_2.parameters)
        position_diff = self._diff_dicts(
            run_1.output_positions, run_2.output_positions
        )

        maximization_objectives = {
            OptimizationObjective.MAXIMIZE_SHARPE,
            OptimizationObjective.MAXIMIZE_DIVERSIFICATION,
        }
        is_maximization = run_1.objective in maximization_objectives

        if is_maximization:
            better_run = run_1 if run_1.objective_value > run_2.objective_value else run_2
        else:
            better_run = run_1 if run_1.objective_value < run_2.objective_value else run_2

        summary: dict[str, Any] = {
            "status": "compared",
            "run_1": self._run_to_dict(run_1),
            "run_2": self._run_to_dict(run_2),
            "parameter_differences": param_diff,
            "position_differences": position_diff,
            "convergence_1_points": len(conv_1),
            "convergence_2_points": len(conv_2),
            "convergence_1_achieved": run_1.convergence_achieved,
            "convergence_2_achieved": run_2.convergence_achieved,
            "run_1_duration_ms": run_1.duration_ms,
            "run_2_duration_ms": run_2.duration_ms,
            "run_1_iterations": run_1.iterations,
            "run_2_iterations": run_2.iterations,
            "better_run_id": better_run.id,
            "better_objective_value": better_run.objective_value,
            "comparison_note": (
                f"Run {better_run.id} achieved a better "
                f"{better_run.objective.value} value of "
                f"{better_run.objective_value:.6f}"
            ),
        }

        if conv_1 and conv_2:
            summary["convergence_1_final_value"] = conv_1[-1].objective_value
            summary["convergence_2_final_value"] = conv_2[-1].objective_value
            summary["convergence_1_initial_value"] = conv_1[0].objective_value
            summary["convergence_2_initial_value"] = conv_2[0].objective_value
            summary["convergence_1_improvement"] = (
                conv_1[0].objective_value - conv_1[-1].objective_value
            )
            summary["convergence_2_improvement"] = (
                conv_2[0].objective_value - conv_2[-1].objective_value
            )

        return summary

    async def get_stats(self) -> OptimizationMemoryStats:
        """
        Compute aggregate statistics from all stored optimization runs.

        Calculates success rates, average iterations and durations,
        best objective values, and breakdowns by optimizer type
        and strategy for dashboard and calibration purposes.

        Returns:
            An OptimizationMemoryStats instance with aggregate metrics.
        """
        stats = OptimizationMemoryStats(total_runs=len(self._runs))

        if not self._runs:
            return stats

        successful = [r for r in self._runs if r.success]
        failed = [r for r in self._runs if not r.success]

        stats.successful_runs = len(successful)
        stats.failed_runs = len(failed)

        if self._runs:
            stats.avg_iterations = round(
                sum(r.iterations for r in self._runs) / len(self._runs), 2
            )
            stats.avg_duration_ms = round(
                sum(r.duration_ms for r in self._runs) / len(self._runs), 2
            )

        sharpe_runs = [
            r
            for r in self._runs
            if r.objective == OptimizationObjective.MAXIMIZE_SHARPE
            and r.success
        ]
        if sharpe_runs:
            stats.best_sharpe = round(
                max(r.objective_value for r in sharpe_runs), 6
            )

        var_runs = [
            r
            for r in self._runs
            if r.objective == OptimizationObjective.MINIMIZE_VAR
            and r.success
        ]
        if var_runs:
            stats.best_var_reduction = round(
                min(r.objective_value for r in var_runs), 6
            )

        optimizer_counts: dict[str, int] = {}
        for r in self._runs:
            t = r.optimizer_type.value
            optimizer_counts[t] = optimizer_counts.get(t, 0) + 1
        stats.by_optimizer = optimizer_counts

        strategy_counts: dict[str, int] = {}
        for r in self._runs:
            s = r.strategy or "UNKNOWN"
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
        stats.by_strategy = strategy_counts

        converged = [r for r in self._runs if r.convergence_achieved]
        if self._runs:
            stats.convergence_rate_pct = round(
                (len(converged) / len(self._runs)) * 100, 2
            )

        return stats

    async def cleanup_old_runs(self, max_age_days: int = 90) -> int:
        """
        Remove optimization runs older than the specified age threshold.

        Deletes runs (and their associated convergence history) that
        are older than max_age_days. This is useful for managing
        memory usage and purging stale optimization data.

        Args:
            max_age_days: Maximum age of runs in days. Runs older than
                this will be removed. Defaults to 90 days.

        Returns:
            The number of runs that were removed.
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)

        before_count = len(self._runs)

        removed_runs = [r for r in self._runs if r.timestamp < cutoff]
        removed_ids = {r.id for r in removed_runs}

        self._runs = [r for r in self._runs if r.timestamp >= cutoff]

        for rid in removed_ids:
            self._convergence.pop(rid, None)

        removed_count = before_count - len(self._runs)

        if removed_count > 0:
            logger.info(
                "Cleaned up %d optimization runs older than %d days",
                removed_count,
                max_age_days,
            )

        return removed_count

    def _find_run(self, run_id: str) -> Optional[OptimizationRun]:
        """
        Find an optimization run by its unique identifier.

        Args:
            run_id: The unique identifier to search for.

        Returns:
            The matching OptimizationRun, or None if not found.
        """
        for r in self._runs:
            if r.id == run_id:
                return r
        return None

    @staticmethod
    def _diff_dicts(
        dict_1: dict[str, Any], dict_2: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compute differences between two dictionaries.

        Identifies keys present in either dictionary with their
        respective values for comparison purposes.

        Args:
            dict_1: First dictionary to compare.
            dict_2: Second dictionary to compare.

        Returns:
            A dictionary with keys from both inputs, showing the
            values from each side and flags for differences.
        """
        all_keys = set(dict_1.keys()) | set(dict_2.keys())
        diff: dict[str, Any] = {}

        for key in sorted(all_keys):
            v1 = dict_1.get(key)
            v2 = dict_2.get(key)
            if v1 != v2:
                diff[key] = {"value_1": v1, "value_2": v2, "different": True}

        return diff

    @staticmethod
    def _run_to_dict(run: OptimizationRun) -> dict[str, Any]:
        """
        Convert an OptimizationRun to a serializable dictionary.

        Args:
            run: The optimization run to convert.

        Returns:
            A dictionary representation of the run with enum values
            converted to their string representations.
        """
        return {
            "id": run.id,
            "portfolio_id": run.portfolio_id,
            "timestamp": run.timestamp.isoformat(),
            "strategy": run.strategy,
            "optimizer_type": run.optimizer_type.value,
            "objective": run.objective.value,
            "parameters": run.parameters,
            "input_positions": run.input_positions,
            "output_positions": run.output_positions,
            "objective_value": run.objective_value,
            "convergence_achieved": run.convergence_achieved,
            "iterations": run.iterations,
            "duration_ms": run.duration_ms,
            "success": run.success,
            "warnings": run.warnings,
        }

    @property
    def total_runs_stored(self) -> int:
        """Total number of optimization runs stored (including trimmed)."""
        return self._total_runs_stored

    @property
    def run_count(self) -> int:
        """Current number of optimization runs in memory."""
        return len(self._runs)

    @property
    def convergence_entries(self) -> int:
        """Current number of convergence history entries in memory."""
        return len(self._convergence)