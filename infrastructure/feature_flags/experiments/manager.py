"""
Experiment manager.

Unified entry point for experiment operations.
Coordinates variant allocation, statistics
collection, analysis, and winner selection.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from .allocator import VariantAllocator
from .analyzer import AnalysisResult, ExperimentAnalyzer
from .archive import ExperimentArchive
from .audit import ExperimentAudit
from .experiment import Experiment, ExperimentResult, ExperimentStatus
from .metrics import ExperimentMetrics
from .statistics import StatisticsCollector, VariantStats
from .validator import ExperimentValidator
from .variant import Variant, create_ab_variants
from .winner import WinnerSelector, WinnerResult


class ExperimentManager:
    """
    Unified experiment management.

    Orchestrates the full experiment lifecycle:
    create → start → allocate → collect → analyze → complete → archive

    Usage:
        manager = ExperimentManager()
        exp = manager.create("exp-1", "Test", "flag-1",
                             variants=create_ab_variants())
        await manager.start("exp-1")
        variant = manager.assign("exp-1", "user-123")
        manager.record_observation("exp-1", "control", value=1.0, converted=True)
        result = await manager.analyze("exp-1")
    """

    def __init__(self) -> None:
        """Initialize the experiment manager."""
        self._experiments: Dict[str, Experiment] = {}
        self._allocator = VariantAllocator()
        self._statistics = StatisticsCollector()
        self._analyzer = ExperimentAnalyzer()
        self._winner_selector = WinnerSelector()
        self._archive = ExperimentArchive()
        self._metrics = ExperimentMetrics()
        self._audit = ExperimentAudit()
        self._validator = ExperimentValidator()
        self._lock = asyncio.Lock()

    def create(
        self,
        experiment_id: str,
        name: str,
        feature_key: str,
        variants: Optional[List[Variant]] = None,
        traffic_percentage: float = 100.0,
    ) -> Experiment:
        """
        Create a new experiment.

        Args:
            experiment_id: Unique experiment identifier.
            name: Human-readable name.
            feature_key: Associated feature flag key.
            variants: Variant definitions.
            traffic_percentage: Traffic percentage to include.

        Returns:
            Experiment instance.
        """
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            feature_key=feature_key,
            variants=variants or create_ab_variants(),
            traffic_percentage=traffic_percentage,
        )
        self._experiments[experiment_id] = experiment
        return experiment

    async def start(self, experiment_id: str) -> bool:
        """
        Start an experiment.

        Args:
            experiment_id: Experiment to start.

        Returns:
            True if started.
        """
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False

        exp.status = ExperimentStatus.RUNNING
        exp.started_at = exp.started_at or exp.created_at
        self._metrics.record_experiment_start(experiment_id)
        await self._audit.record_start(experiment_id, exp.feature_key)
        return True

    async def pause(self, experiment_id: str) -> bool:
        """Pause an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return False
        exp.status = ExperimentStatus.PAUSED
        return True

    async def resume(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.PAUSED:
            return False
        exp.status = ExperimentStatus.RUNNING
        return True

    def assign(
        self,
        experiment_id: str,
        target_id: str,
    ) -> Optional[Variant]:
        """
        Assign a target to a variant.

        Args:
            experiment_id: Experiment identifier.
            target_id: Target identifier.

        Returns:
            Assigned Variant or None.
        """
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return None

        variant = self._allocator.assign(
            experiment_id, target_id, exp.variants,
        )
        self._metrics.record_variant_assignment(
            experiment_id, variant.variant_id,
        )
        return variant

    def record_observation(
        self,
        experiment_id: str,
        variant_id: str,
        value: float = 1.0,
        converted: bool = False,
        custom_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record an observation for a variant.

        Args:
            experiment_id: Experiment identifier.
            variant_id: Variant identifier.
            value: Metric value.
            converted: Whether a conversion occurred.
            custom_metrics: Additional metrics.
        """
        self._statistics.record(
            variant_id, value=value, converted=converted,
            custom_metrics=custom_metrics,
        )

    async def analyze(
        self,
        experiment_id: str,
        confidence: float = 0.95,
        metric_type: str = "conversion",
    ) -> Optional[AnalysisResult]:
        """
        Analyze experiment results.

        Args:
            experiment_id: Experiment to analyze.
            confidence: Desired confidence level.
            metric_type: Metric type for analysis.

        Returns:
            AnalysisResult or None.
        """
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None

        # Get stats per variant
        all_stats = self._statistics.get_all_stats()
        control = None
        treatments = []

        for variant in exp.variants:
            stats = all_stats.get(variant.variant_id)
            if not stats:
                continue
            if variant.is_control:
                control = stats
            else:
                treatments.append(stats)

        if not control or not treatments:
            return None

        # Analyze control vs first treatment
        return self._analyzer.analyze(
            control, treatments[0],
            confidence=confidence,
            metric_type=metric_type,
        )

    async def complete(
        self,
        experiment_id: str,
        winner_id: Optional[str] = None,
    ) -> Optional[ExperimentResult]:
        """
        Complete an experiment.

        Args:
            experiment_id: Experiment to complete.
            winner_id: Optional manual winner selection.

        Returns:
            ExperimentResult or None.
        """
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None

        # Auto-select winner if not specified
        if not winner_id:
            analysis = await self.analyze(experiment_id)
            if analysis and analysis.is_significant:
                # Find treatment variant
                all_stats = self._statistics.get_all_stats()
                for variant in exp.variants:
                    if not variant.is_control:
                        stats = all_stats.get(variant.variant_id)
                        control_stats = all_stats.get(
                            next((v.variant_id for v in exp.variants if v.is_control), ""),
                            VariantStats(),
                        )
                        if stats and stats.average_value > control_stats.average_value:
                            winner_id = variant.variant_id
                            break
                if not winner_id:
                    winner_id = ""

        exp.status = ExperimentStatus.COMPLETED
        exp.winner_variant_id = winner_id or ""
        exp.completed_at = exp.completed_at or exp.created_at

        # Calculate duration
        duration = 0.0
        if exp.started_at and exp.completed_at:
            delta = exp.completed_at - exp.started_at
            duration = delta.total_seconds()
        self._metrics.record_experiment_duration(experiment_id, duration)

        # Archive
        result_data = {"winner_id": winner_id, "analysis_available": True}
        await self._archive.store(exp, result_data)
        await self._audit.record_completion(experiment_id, winner_id or "")

        return ExperimentResult(
            experiment_id=experiment_id,
            winner_variant_id=winner_id or "",
        )

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def get_variant_stats(self, variant_id: str) -> Optional[VariantStats]:
        """Get statistics for a variant."""
        return self._statistics.get_stats(variant_id)

    def validate_experiment(self, experiment: Experiment) -> List[str]:
        """Validate an experiment configuration."""
        return self._validator.validate_experiment(experiment)

    @property
    def allocator(self) -> VariantAllocator:
        """Access the variant allocator."""
        return self._allocator

    @property
    def archive(self) -> ExperimentArchive:
        """Access the experiment archive."""
        return self._archive

    @property
    def metrics(self) -> ExperimentMetrics:
        """Access experiment metrics."""
        return self._metrics

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_experiments": len(self._experiments),
            "running": sum(
                1 for e in self._experiments.values()
                if e.status == ExperimentStatus.RUNNING
            ),
            "completed": sum(
                1 for e in self._experiments.values()
                if e.status == ExperimentStatus.COMPLETED
            ),
            "allocator_stats": self._allocator.get_stats(),
            "metrics_snapshot": self._metrics.snapshot(),
        }
