"""
Strategy Signal Aggregator — Combine Signals from All Strategies

Collects signals from all active strategies and produces a unified
signal map. Handles multi-strategy signal aggregation, weighting by
confidence, priority, and capital allocation.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AggregatedSignal:
    asset: str
    net_signal: float  # Positive = BUY, Negative = SELL
    gross_signal: float  # Sum of absolute signals
    confidence: float
    contributors: int
    breakdown: Dict[str, float] = field(default_factory=dict)


class StrategySignalAggregator:
    """
    Collects and aggregates signals from all active strategies.

    Produces per-asset unified signals for downstream netting.
    """

    def __init__(
        self,
        aggregator_id: Optional[str] = None,
        registry=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.aggregator_id = aggregator_id or f"ssa-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self.config = config or {}
        self._raw_signals: Dict[str, Dict[str, float]] = {}
        self._aggregated: Dict[str, AggregatedSignal] = {}

    def submit(self, strategy_id: str, signals: Dict[str, float]) -> None:
        """Submit raw signals from a strategy: {asset: signal_strength}."""
        self._raw_signals[strategy_id] = signals

    def aggregate(self) -> Dict[str, AggregatedSignal]:
        """Aggregate all signals into unified per-asset signals."""
        self._aggregated.clear()
        asset_signals: Dict[str, Dict[str, float]] = {}

        for sid, signals in self._raw_signals.items():
            weight = self._get_strategy_weight(sid)
            for asset, sig in signals.items():
                asset_signals.setdefault(asset, {})[sid] = sig * weight

        for asset, contributors in asset_signals.items():
            net = sum(contributors.values())
            gross = sum(abs(v) for v in contributors.values())
            conf = min(1.0, len(contributors) / 5.0)

            self._aggregated[asset] = AggregatedSignal(
                asset=asset,
                net_signal=net,
                gross_signal=gross,
                confidence=conf,
                contributors=len(contributors),
                breakdown=contributors,
            )

        return self._aggregated

    def _get_strategy_weight(self, strategy_id: str) -> float:
        if self._registry:
            rec = self._registry.get(strategy_id)
            if rec and rec.capital_allocation > 0:
                total = self._registry.get_total_capital()
                return rec.capital_allocation / total if total > 0 else 1.0
        return 1.0

    def get(self, asset: str) -> Optional[AggregatedSignal]:
        return self._aggregated.get(asset)

    def get_all(self) -> Dict[str, AggregatedSignal]:
        return dict(self._aggregated)
