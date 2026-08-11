"""
Signal Netting Engine — Cross-Strategy Signal Cancellation

Before placing orders, net opposing signals at the portfolio level:

    Strategy A → BUY  +100
    Strategy B → BUY  +80
    Strategy C → SELL -50
    ─────────────────────
    Net Signal  → BUY  +130

This reduces unnecessary turnover, commissions, spread, and market impact.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NettedSignal:
    asset: str
    gross_buy: float
    gross_sell: float
    net_signal: float
    savings_pct: float  # Reduction vs gross
    original_contributors: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SignalNettingEngine:
    """
    Nets opposing signals across all strategies.

    Key value: replaces N independent orders with 1 net order,
    reducing costs and market impact.
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"sne-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._netted: Dict[str, NettedSignal] = {}
        self._min_net_threshold = self.config.get("min_net_threshold", 0.001)

    def net(self, aggregated_signals: Dict[str, Any]) -> Dict[str, NettedSignal]:
        """
        Net aggregated signals into final per-asset signals.

        Input: {asset: AggregatedSignal}
        Output: {asset: NettedSignal}
        """
        self._netted.clear()

        for asset, sig in aggregated_signals.items():
            gross_buy = 0.0
            gross_sell = 0.0

            for sid, val in (sig.breakdown if hasattr(sig, 'breakdown') else {}).items():
                if val > 0:
                    gross_buy += val
                else:
                    gross_sell += abs(val)

            gross_total = gross_buy + gross_sell
            net = sig.net_signal if hasattr(sig, 'net_signal') else gross_buy - gross_sell

            savings = 0.0
            if gross_total > 0:
                savings = 1.0 - (abs(net) / gross_total if gross_total > 0 else 1.0)

            if abs(net) >= self._min_net_threshold:
                self._netted[asset] = NettedSignal(
                    asset=asset,
                    gross_buy=gross_buy,
                    gross_sell=gross_sell,
                    net_signal=net,
                    savings_pct=savings,
                    original_contributors=len(sig.breakdown) if hasattr(sig, 'breakdown') else 1,
                )

        return self._netted

    def get(self, asset: str) -> Optional[NettedSignal]:
        return self._netted.get(asset)

    def get_total_savings(self) -> float:
        """Total turnover reduction from netting."""
        total_gross = sum(s.gross_buy + s.gross_sell for s in self._netted.values())
        total_net = sum(abs(s.net_signal) for s in self._netted.values())
        return 1.0 - (total_net / total_gross) if total_gross > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "netted_assets": len(self._netted),
            "total_savings_pct": self.get_total_savings(),
            "signals": {a: s.net_signal for a, s in self._netted.items()},
        }
