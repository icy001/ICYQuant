"""
Portfolio Weight Engine — Asset Weight Computation & Management

Manages portfolio weights: normalization, capping, re-scaling.
Handles weight drift detection and target weight computation.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WeightConfig:
    asset: str
    target_weight: float = 0.0
    current_weight: float = 0.0
    min_weight: float = 0.0
    max_weight: float = 0.10
    drift: float = 0.0


class PortfolioWeightEngine:
    """
    Manages portfolio asset weights with constraints.

    Handles: normalization, drift detection, weight capping, re-scaling.
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"pwe-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._max_single_weight = self.config.get("max_single_weight", 0.10)
        self._drift_threshold = self.config.get("drift_threshold", 0.02)
        self._weights: Dict[str, WeightConfig] = {}

    def set_target_weights(self, weights: Dict[str, float]) -> None:
        """Set target weights, auto-capping at max_single_weight."""
        total = sum(weights.values())
        for asset, w in weights.items():
            capped = min(w / total if total > 0 else 0, self._max_single_weight)
            self._weights[asset] = WeightConfig(
                asset=asset,
                target_weight=capped,
                current_weight=self._weights.get(asset, WeightConfig(asset=asset)).current_weight,
            )
        # Re-normalize after capping
        self._normalize()

    def update_current(self, current: Dict[str, float]) -> None:
        """Update current weights and compute drift."""
        for asset, w in current.items():
            config = self._weights.get(asset)
            if config:
                config.current_weight = w
                config.drift = w - config.target_weight
            else:
                self._weights[asset] = WeightConfig(asset=asset, current_weight=w, drift=w)

    def detect_drifted_assets(self) -> Dict[str, float]:
        """Find assets where weight exceeds drift threshold."""
        return {
            asset: config.drift
            for asset, config in self._weights.items()
            if abs(config.drift) > self._drift_threshold
        }

    def get_total_drift(self) -> float:
        return sum(abs(c.drift) for c in self._weights.values())

    def _normalize(self) -> None:
        total = sum(c.target_weight for c in self._weights.values())
        if total > 0:
            for c in self._weights.values():
                c.target_weight /= total

    def get_summary(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "assets": len(self._weights),
            "total_drift": self.get_total_drift(),
            "drifted": self.detect_drifted_assets(),
        }
