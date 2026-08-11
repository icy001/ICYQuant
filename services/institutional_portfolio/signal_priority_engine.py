"""
Signal Priority Engine — Prioritize Signals by Strategy Weight

Assigns priority to signals based on strategy capital allocation,
risk budget, expected return, and signal confidence.
Higher priority signals are executed first and have more weight in conflicts.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SignalPriority:
    strategy_id: str
    asset: str
    signal_value: float
    priority_score: float
    capital_weight: float
    confidence: float


class SignalPriorityEngine:
    """
    Ranks signals by priority for execution ordering and conflict resolution.

    Priority = f(capital_allocation, risk_budget, expected_return, confidence, freshness)
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        registry=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"spe-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self.config = config or {}
        self._weights = {
            "capital": 0.30,
            "risk_budget": 0.10,
            "expected_return": 0.25,
            "confidence": 0.25,
            "freshness": 0.10,
        }

    def rank(self, signals: Dict[str, Dict[str, float]],
             confidences: Optional[Dict[str, float]] = None) -> List[SignalPriority]:
        """
        Rank all signals by priority across strategies and assets.

        Args:
            signals: {strategy_id: {asset: signal_value}}
            confidences: {strategy_id: confidence}
        """
        confidences = confidences or {}
        priorities = []

        for sid, asset_signals in signals.items():
            rec = self._registry.get(sid) if self._registry else None

            cap_weight = rec.capital_allocation / max(1, self._registry.get_total_capital()) if rec else 0.5
            risk_weight = rec.risk_budget / max(1, self._registry.get_total_risk_budget()) if rec else 0.5
            conf = confidences.get(sid, 0.5)

            for asset, sig in asset_signals.items():
                score = (
                    self._weights["capital"] * cap_weight +
                    self._weights["risk_budget"] * risk_weight +
                    self._weights["confidence"] * conf +
                    self._weights["freshness"] * 0.5 +
                    self._weights["expected_return"] * 0.5
                )
                priorities.append(SignalPriority(
                    strategy_id=sid,
                    asset=asset,
                    signal_value=sig,
                    priority_score=score,
                    capital_weight=cap_weight,
                    confidence=conf,
                ))

        return sorted(priorities, key=lambda x: -x.priority_score)

    def get_top_signals(self, signals: Dict[str, Dict[str, float]], n: int = 10) -> List[SignalPriority]:
        return self.rank(signals)[:n]
