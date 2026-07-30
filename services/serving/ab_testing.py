"""A/B Testing — controlled experiments for model comparison.

Splits prediction traffic between model variants (e.g., v37 vs v38)
and collects performance statistics for statistical comparison.

Usage::

    ab = ABTesting(config=ABConfig())
    ab.create_experiment("v37_vs_v38", variants=[
        ABVariant(name="v37", model_name="alpha_v37", traffic_share=0.9),
        ABVariant(name="v38", model_name="alpha_v38", traffic_share=0.1),
    ])
    variant = ab.select_variant("NVDA", experiment="v37_vs_v38")
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ABStatus(str, Enum):
    """A/B experiment status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ABVariant:
    """A variant (arm) in an A/B test.

    Attributes:
        name: Variant name (e.g., "control", "champion", "v38").
        model_name: Model in the registry.
        traffic_share: Fraction of traffic [0, 1].
        description: Human-readable description.
    """

    name: str
    model_name: str
    traffic_share: float = 0.5
    description: str = ""


@dataclass
class ABResult:
    """Aggregated results for an A/B experiment variant.

    Attributes:
        variant_name: Variant identifier.
        prediction_count: Number of predictions served.
        avg_prediction: Mean prediction value.
        avg_confidence: Mean confidence.
        pnl_cumulative: Cumulative PnL if tracked.
        sharpe: Sharpe ratio if tracked.
        accuracy: Accuracy if labels available.
        latency_ms_avg: Average prediction latency.
    """

    variant_name: str = ""
    prediction_count: int = 0
    avg_prediction: float = 0.0
    avg_confidence: float = 0.0
    pnl_cumulative: float = 0.0
    sharpe: float = 0.0
    accuracy: float = 0.0
    latency_ms_avg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_name": self.variant_name,
            "prediction_count": self.prediction_count,
            "avg_prediction": round(self.avg_prediction, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "pnl_cumulative": round(self.pnl_cumulative, 4),
            "sharpe": round(self.sharpe, 4),
            "accuracy": round(self.accuracy, 4),
            "latency_ms_avg": round(self.latency_ms_avg, 3),
        }


@dataclass
class ABExperiment:
    """An A/B test experiment.

    Attributes:
        experiment_id: Unique experiment identifier.
        name: Human-readable name.
        variants: List of A/B variants.
        status: Current experiment status.
        created_at: Creation timestamp.
        started_at: When experiment started.
        ended_at: When experiment ended or was concluded.
        description: Experiment purpose and hypothesis.
    """

    experiment_id: str = ""
    name: str = ""
    variants: List[ABVariant] = field(default_factory=list)
    status: ABStatus = ABStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    description: str = ""


@dataclass
class ABConfig:
    """A/B testing configuration.

    Attributes:
        default_traffic_split: Default champion traffic share.
        min_sample_size: Minimum predictions before significance test.
        significance_level: p-value threshold for declaring winner.
        tracking_window_days: How many days to track results.
        auto_conclude: Automatically stop when significance reached.
    """

    default_traffic_split: float = 0.9
    min_sample_size: int = 1000
    significance_level: float = 0.05
    tracking_window_days: int = 7
    auto_conclude: bool = False


class ABTesting:
    """A/B Testing manager for model variants.

    Manages multiple experiments, splits traffic using consistent
    hashing (by symbol), and tracks per-variant statistics.

    Usage::

        ab = ABTesting(config=ABConfig())
        ab.create_experiment("exp1", [
            ABVariant("champion", "alpha_v37", 0.9),
            ABVariant("challenger", "alpha_v38", 0.1),
        ])
        ab.start("exp1")
        variant = ab.select_variant("NVDA", "exp1")
    """

    def __init__(self, config: Optional[ABConfig] = None):
        self.config = config or ABConfig()
        self._experiments: Dict[str, ABExperiment] = {}
        self._results: Dict[str, Dict[str, ABResult]] = {}  # exp_id → variant_name → result
        self._prediction_log: List[Dict[str, Any]] = []

    def create_experiment(
        self,
        name: str,
        variants: List[ABVariant],
        description: str = "",
    ) -> ABExperiment:
        """Create a new A/B experiment.

        Args:
            name: Experiment name (unique identifier).
            variants: List of variants with traffic shares.
            description: Experiment description.

        Returns:
            The created ABExperiment.

        Raises:
            ValueError: If traffic shares don't sum to ~1.0.
        """
        total_share = sum(v.traffic_share for v in variants)
        if abs(total_share - 1.0) > 0.001:
            raise ValueError(f"Traffic shares must sum to 1.0, got {total_share}")

        exp_id = hashlib.md5(name.encode()).hexdigest()[:12]
        experiment = ABExperiment(
            experiment_id=exp_id,
            name=name,
            variants=variants,
            description=description,
        )
        self._experiments[name] = experiment
        self._results[name] = {v.name: ABResult(variant_name=v.name) for v in variants}
        return experiment

    def start(self, name: str) -> None:
        """Start a running A/B experiment."""
        exp = self._experiments.get(name)
        if exp is None:
            raise ValueError(f"Experiment '{name}' not found")
        exp.status = ABStatus.RUNNING
        exp.started_at = time.time()

    def pause(self, name: str) -> None:
        """Pause an experiment without discarding data."""
        exp = self._experiments.get(name)
        if exp is None:
            raise ValueError(f"Experiment '{name}' not found")
        exp.status = ABStatus.PAUSED

    def complete(self, name: str, winner: Optional[str] = None) -> Dict[str, Any]:
        """Complete an experiment and declare winner."""
        exp = self._experiments.get(name)
        if exp is None:
            raise ValueError(f"Experiment '{name}' not found")
        exp.status = ABStatus.COMPLETED
        exp.ended_at = time.time()

        summary = self.get_results(name)
        if winner is None and summary:
            # Auto-select winner based on avg_prediction or other metric
            best = max(summary, key=lambda v: summary[v].avg_prediction)
            winner = best

        return {"experiment": name, "winner": winner, "results": {k: v.to_dict() for k, v in summary.items()}}

    def select_variant(self, symbol: str, experiment_name: str) -> Optional[ABVariant]:
        """Select a variant for prediction using consistent hashing.

        Uses the symbol as the hash key so the same symbol always
        goes to the same variant within an experiment.

        Args:
            symbol: Trading symbol (used for consistent hashing).
            experiment_name: Experiment identifier.

        Returns:
            Selected ABVariant or None.
        """
        exp = self._experiments.get(experiment_name)
        if exp is None or exp.status != ABStatus.RUNNING:
            return None

        # Consistent hashing: map symbol to [0, 1)
        hash_val = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF

        cumulative = 0.0
        for variant in exp.variants:
            cumulative += variant.traffic_share
            if hash_val < cumulative:
                return variant

        # Fallback to last variant
        return exp.variants[-1] if exp.variants else None

    def record_prediction(
        self,
        experiment_name: str,
        variant_name: str,
        symbol: str,
        prediction: float,
        confidence: float,
        latency_ms: float = 0.0,
    ) -> None:
        """Record a prediction result for A/B tracking.

        Args:
            experiment_name: Experiment identifier.
            variant_name: Which variant produced the prediction.
            symbol: Trading symbol.
            prediction: Model prediction value.
            confidence: Prediction confidence.
            latency_ms: Inference latency.
        """
        if experiment_name not in self._results:
            return

        results = self._results[experiment_name]
        if variant_name not in results:
            return

        r = results[variant_name]
        n = r.prediction_count
        r.avg_prediction = (r.avg_prediction * n + prediction) / (n + 1)
        r.avg_confidence = (r.avg_confidence * n + confidence) / (n + 1)
        r.latency_ms_avg = (r.latency_ms_avg * n + latency_ms) / (n + 1)
        r.prediction_count = n + 1

        self._prediction_log.append({
            "experiment": experiment_name,
            "variant": variant_name,
            "symbol": symbol,
            "prediction": prediction,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        })

    def get_results(self, name: str) -> Dict[str, ABResult]:
        """Get current results for an experiment.

        Returns:
            Dict mapping variant_name → ABResult.
        """
        return self._results.get(name, {})

    def list_experiments(self) -> List[ABExperiment]:
        """List all experiments."""
        return list(self._experiments.values())

    def get_experiment(self, name: str) -> Optional[ABExperiment]:
        """Get experiment by name."""
        return self._experiments.get(name)

    def delete_experiment(self, name: str) -> bool:
        """Delete an experiment and its results."""
        if name in self._experiments:
            del self._experiments[name]
            self._results.pop(name, None)
            return True
        return False
