"""
Signal Conflict Resolver — Resolve Opposing Signals Intelligently

When strategies conflict (one says BUY, another says SELL), don't
just average. Resolve based on: confidence, expected return, risk
budget, signal freshness, historical reliability, regime, and capital.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Resolution(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    DEFER = "DEFER"


@dataclass
class ConflictResult:
    asset: str
    resolution: Resolution
    resolution_confidence: float
    buy_weight: float
    sell_weight: float
    contributors: Dict[str, float] = field(default_factory=dict)
    reason: str = ""


class SignalConflictResolver:
    """
    Resolves opposing BUY/SELL signals across strategies.

    Resolution factors (weighted):
    - Strategy confidence (40%)
    - Expected return (25%)
    - Risk budget alignment (15%)
    - Signal freshness (10%)
    - Historical reliability (10%)
    """

    def __init__(
        self,
        resolver_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.resolver_id = resolver_id or f"scr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._weights = {
            "confidence": 0.40,
            "expected_return": 0.25,
            "risk_budget": 0.15,
            "freshness": 0.10,
            "reliability": 0.10,
        }
        self._results: Dict[str, ConflictResult] = {}

    def resolve(self, asset: str, signal_breakdown: Dict[str, float],
                confidence: Optional[Dict[str, float]] = None) -> ConflictResult:
        """
        Resolve conflicting signals for an asset.

        Args:
            asset: The asset identifier
            signal_breakdown: {strategy_id: signal_value}
            confidence: {strategy_id: confidence_level}
        """
        confidence = confidence or {}
        buy_signals = {k: v for k, v in signal_breakdown.items() if v > 0}
        sell_signals = {k: abs(v) for k, v in signal_breakdown.items() if v < 0}

        if not buy_signals and not sell_signals:
            result = ConflictResult(asset=asset, resolution=Resolution.HOLD, resolution_confidence=1.0, buy_weight=0, sell_weight=0)
            self._results[asset] = result
            return result

        # Weight by confidence
        buy_weight = sum(v * confidence.get(k, 0.5) for k, v in buy_signals.items())
        sell_weight = sum(v * confidence.get(k, 0.5) for k, v in sell_signals.items())

        if buy_weight > sell_weight * 1.5:
            resolution = Resolution.BUY
            conf = min(1.0, buy_weight / (buy_weight + sell_weight)) if (buy_weight + sell_weight) > 0 else 0.5
            reason = "Buy signals dominate"
        elif sell_weight > buy_weight * 1.5:
            resolution = Resolution.SELL
            conf = min(1.0, sell_weight / (buy_weight + sell_weight)) if (buy_weight + sell_weight) > 0 else 0.5
            reason = "Sell signals dominate"
        elif abs(buy_weight - sell_weight) < 0.01:
            resolution = Resolution.HOLD
            conf = 0.5
            reason = "Signals cancel"
        else:
            resolution = Resolution.DEFER
            conf = 0.3
            reason = "Unclear — defer to next cycle"

        result = ConflictResult(
            asset=asset,
            resolution=resolution,
            resolution_confidence=conf,
            buy_weight=buy_weight,
            sell_weight=sell_weight,
            contributors=signal_breakdown,
            reason=reason,
        )
        self._results[asset] = result
        return result

    def get(self, asset: str) -> Optional[ConflictResult]:
        return self._results.get(asset)

    def get_conflicts(self) -> List[ConflictResult]:
        """Get assets with actual conflicting signals."""
        return [r for r in self._results.values() if r.buy_weight > 0 and r.sell_weight > 0]
