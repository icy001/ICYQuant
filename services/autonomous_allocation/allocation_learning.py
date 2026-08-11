"""Allocation Learning — adaptive model improvement from feedback.

Pipeline:
    Prediction → Allocation → Execution → Outcome → Error → Model Adjustment

Uses prediction errors to adjust model parameters over time,
moving toward adaptive capital allocation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ModelAdjustment:
    """A suggested model parameter adjustment."""
    model_name: str
    parameter: str
    current_value: float = 0.0
    suggested_value: float = 0.0
    confidence: float = 0.0
    evidence_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LearningState:
    """Current state of the learning system."""
    adjustments: Dict[str, ModelAdjustment] = field(default_factory=dict)
    total_feedback_events: int = 0
    model_versions: Dict[str, int] = field(default_factory=dict)
    last_update: Optional[datetime] = None


class AllocationLearning:
    """Adaptive learning system for allocation model improvement.

    Tracks prediction errors over time and suggests model
    parameter adjustments to reduce systematic bias.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._learning_rate = self._config.get("learning_rate", 0.10)
        self._min_samples = self._config.get("min_samples", 20)
        self._state = LearningState()

        # Error accumulation buffers
        self._alpha_errors: List[float] = []
        self._risk_errors: List[float] = []
        self._impact_errors: List[float] = []
        self._slippage_errors: List[float] = []
        self._cost_errors: List[float] = []
        self._max_buffer = 500

    def ingest_feedback(self, predicted: Dict[str, float],
                        realized: Dict[str, float]) -> None:
        """Ingest a feedback event and accumulate errors."""
        if "alpha" in predicted and "alpha" in realized:
            self._alpha_errors.append(realized["alpha"] - predicted["alpha"])
        if "risk" in predicted and "risk" in realized:
            self._risk_errors.append(realized["risk"] - predicted["risk"])
        if "impact" in predicted and "impact" in realized:
            self._impact_errors.append(realized["impact"] - predicted["impact"])
        if "slippage" in predicted and "slippage" in realized:
            self._slippage_errors.append(realized["slippage"] - predicted["slippage"])
        if "cost" in predicted and "cost" in realized:
            self._cost_errors.append(realized["cost"] - predicted["cost"])

        # Trim buffers
        self._trim_buffers()
        self._state.total_feedback_events += 1

    def _trim_buffers(self) -> None:
        """Keep error buffers at max size."""
        if len(self._alpha_errors) > self._max_buffer:
            self._alpha_errors = self._alpha_errors[-self._max_buffer:]
        if len(self._risk_errors) > self._max_buffer:
            self._risk_errors = self._risk_errors[-self._max_buffer:]
        if len(self._impact_errors) > self._max_buffer:
            self._impact_errors = self._impact_errors[-self._max_buffer:]
        if len(self._slippage_errors) > self._max_buffer:
            self._slippage_errors = self._slippage_errors[-self._max_buffer:]
        if len(self._cost_errors) > self._max_buffer:
            self._cost_errors = self._cost_errors[-self._max_buffer:]

    def compute_adjustments(self) -> List[ModelAdjustment]:
        """Compute suggested model adjustments from accumulated errors."""
        adjustments = []

        # Alpha model bias
        if len(self._alpha_errors) >= self._min_samples:
            bias = sum(self._alpha_errors) / len(self._alpha_errors)
            adj = ModelAdjustment(
                model_name="alpha_model",
                parameter="bias_correction",
                current_value=0.0,
                suggested_value=-bias * self._learning_rate,
                confidence=min(1.0, len(self._alpha_errors) / 100.0),
                evidence_count=len(self._alpha_errors),
            )
            adjustments.append(adj)

        # Impact model scale
        if len(self._impact_errors) >= self._min_samples:
            avg_error = sum(self._impact_errors) / len(self._impact_errors)
            adj = ModelAdjustment(
                model_name="impact_model",
                parameter="scale_factor",
                current_value=1.0,
                suggested_value=1.0 - avg_error * self._learning_rate,
                confidence=min(1.0, len(self._impact_errors) / 100.0),
                evidence_count=len(self._impact_errors),
            )
            adjustments.append(adj)

        # Slippage model
        if len(self._slippage_errors) >= self._min_samples:
            avg_error = sum(self._slippage_errors) / len(self._slippage_errors)
            adj = ModelAdjustment(
                model_name="slippage_model",
                parameter="slippage_factor",
                current_value=0.5,
                suggested_value=0.5 * (1.0 + avg_error * self._learning_rate),
                confidence=min(1.0, len(self._slippage_errors) / 100.0),
                evidence_count=len(self._slippage_errors),
            )
            adjustments.append(adj)

        # Cost model
        if len(self._cost_errors) >= self._min_samples:
            avg_error = sum(self._cost_errors) / len(self._cost_errors)
            adj = ModelAdjustment(
                model_name="cost_model",
                parameter="cost_bias",
                current_value=0.0,
                suggested_value=-avg_error * self._learning_rate,
                confidence=min(1.0, len(self._cost_errors) / 100.0),
                evidence_count=len(self._cost_errors),
            )
            adjustments.append(adj)

        # Update state
        for adj in adjustments:
            key = f"{adj.model_name}.{adj.parameter}"
            self._state.adjustments[key] = adj
        self._state.last_update = datetime.utcnow()

        return adjustments

    def get_state(self) -> LearningState:
        """Get current learning state."""
        return self._state

    def reset(self) -> None:
        """Reset all learning buffers."""
        self._alpha_errors.clear()
        self._risk_errors.clear()
        self._impact_errors.clear()
        self._slippage_errors.clear()
        self._cost_errors.clear()
        self._state = LearningState()
