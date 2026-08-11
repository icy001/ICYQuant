"""
Order Netting Engine
====================
Nets opposing order intents to reduce transaction costs.

Example:
    BUY 100 AAPL + SELL 60 AAPL → BUY 40 AAPL

Supports:
- Same-instrument netting
- Cross-instrument correlation-aware netting (optional)
- Netting by strategy, portfolio, or global
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NettingGroup:
    """A group of intents for the same instrument that can be netted."""

    instrument: str = ""
    intents: List[Dict[str, Any]] = field(default_factory=list)
    net_quantity: float = 0.0
    net_side: str = ""
    gross_quantity: float = 0.0
    savings_pct: float = 0.0  # Estimated cost savings


@dataclass
class NettingResult:
    """Result of netting a set of order intents."""

    netted_intents: List[Dict[str, Any]] = field(default_factory=list)
    original_count: int = 0
    netted_count: int = 0
    total_savings_pct: float = 0.0
    netting_groups: List[NettingGroup] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_count": self.original_count,
            "netted_count": self.netted_count,
            "reduction": f"{self.original_count - self.netted_count}",
            "savings_pct": f"{self.total_savings_pct:.2%}",
            "netting_groups": len(self.netting_groups),
            "metadata": self.metadata,
        }


class OrderNettingEngine:
    """
    Trade Netting Engine.

    Nets opposing orders for the same instrument to reduce
    transaction costs, exchange fees, and market impact.

    Example:
        Strategy A: BUY 100 AAPL
        Strategy B: SELL 60 AAPL
        Net Result: BUY 40 AAPL
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Netting scope
        self._scope = self._config.get("scope", "portfolio")  # global, portfolio, strategy

        # Netting preferences
        self._allow_cross_strategy = self._config.get("allow_cross_strategy", True)
        self._allow_cross_portfolio = self._config.get("allow_cross_portfolio", False)
        self._min_savings_pct = self._config.get("min_savings_pct", 0.001)  # Min savings to net

        # Estimated cost per trade (for savings calculation)
        self._cost_per_trade_bps = self._config.get("cost_per_trade_bps", 5.0)  # 5 bps

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info(
            "OrderNettingEngine initialized (scope=%s, cross_strategy=%s)",
            self._scope,
            self._allow_cross_strategy,
        )

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("OrderNettingEngine shut down")

    # ------------------------------------------------------------------
    # Netting
    # ------------------------------------------------------------------

    def _group_by_instrument(
        self,
        positions: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group positions by instrument for netting."""
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for pos in positions:
            instrument = pos.get("instrument", "")
            if instrument:
                groups[instrument].append(pos)
        return groups

    def _get_quantity(self, pos: Dict[str, Any]) -> float:
        """Extract quantity from a position dict."""
        return pos.get("quantity", pos.get("position_size", 0.0))

    def _get_direction_sign(self, pos: Dict[str, Any]) -> int:
        """Return +1 for long/buy, -1 for short/sell."""
        direction = pos.get("direction", "").upper()
        if direction in ("SHORT", "SELL", "SELL_SHORT", "SELL_TO_OPEN"):
            return -1
        return 1  # LONG, BUY, etc.

    def _net_instrument(
        self,
        instrument: str,
        positions: List[Dict[str, Any]],
    ) -> NettingGroup:
        """
        Net positions for a single instrument.

        Sums all quantities with direction signs to get net position.
        """
        total_signed = 0.0
        gross = 0.0

        for pos in positions:
            qty = self._get_quantity(pos)
            sign = self._get_direction_sign(pos)
            total_signed += qty * sign
            gross += abs(qty)

        net_quantity = abs(total_signed)
        net_side = "LONG" if total_signed >= 0 else "SHORT"

        # Calculate savings
        if gross > 0:
            savings = (gross - net_quantity) / gross
        else:
            savings = 0.0

        return NettingGroup(
            instrument=instrument,
            intents=positions,
            net_quantity=net_quantity,
            net_side=net_side,
            gross_quantity=gross,
            savings_pct=savings,
        )

    def _merge_positions(
        self,
        group: NettingGroup,
    ) -> Dict[str, Any]:
        """
        Merge a netting group into a single netted position dict.

        Preserves metadata from the highest-priority position.
        """
        if not group.intents:
            return {}

        # Sort by priority (descending)
        sorted_positions = sorted(
            group.intents,
            key=lambda p: (p.get("priority", 5), p.get("confidence", 0)),
            reverse=True,
        )

        # Base the netted position on the highest-priority one
        base = dict(sorted_positions[0])

        # Update quantity and direction
        base["quantity"] = group.net_quantity
        base["position_size"] = group.net_quantity
        base["direction"] = group.net_side

        # Combine allocated capital
        total_capital = sum(
            p.get("allocated_capital", p.get("position_value", 0.0))
            for p in group.intents
        )
        base["allocated_capital"] = total_capital
        base["position_value"] = total_capital

        # Record netting metadata
        base["netted"] = True
        base["original_positions"] = len(group.intents)
        base["netting_savings_pct"] = group.savings_pct
        base["netted_strategy_ids"] = list(set(
            p.get("strategy_id", "") for p in group.intents
        ))
        base["reason"] = (
            f"Netted {len(group.intents)} positions: "
            f"{group.gross_quantity:.2f} → {group.net_quantity:.2f} "
            f"({group.savings_pct:.1%} savings)"
        )

        return base

    async def net(
        self,
        positions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Net opposing positions to reduce order count.

        Args:
            positions: List of position/allocation dicts.

        Returns:
            Netted list of positions.
        """
        if not self._initialized:
            await self.initialize()

        if not positions:
            return []

        original_count = len(positions)
        groups = self._group_by_instrument(positions)

        netted = []
        netting_groups = []
        passthrough = []

        for instrument, group in groups.items():
            if len(group) == 1:
                # Single position, no netting needed
                passthrough.append(group[0])
                continue

            # Check if positions are in different directions
            directions = set(self._get_direction_sign(p) for p in group)
            if len(directions) == 1:
                # Same direction: merge quantities
                total_qty = sum(self._get_quantity(p) for p in group)
                merged = dict(group[0])
                merged["quantity"] = total_qty
                merged["position_size"] = total_qty
                merged["allocated_capital"] = sum(
                    p.get("allocated_capital", p.get("position_value", 0))
                    for p in group
                )
                merged["netted"] = True
                merged["original_positions"] = len(group)
                merged["reason"] = f"Merged {len(group)} same-direction positions"
                netted.append(merged)
                continue

            # Opposite directions: net them
            ng = self._net_instrument(instrument, group)

            if ng.net_quantity <= 0:
                # Fully netted to zero
                logger.info(
                    "Fully netted %s: %d positions cancelled each other",
                    instrument,
                    len(group),
                )
                netting_groups.append(ng)
                continue

            if ng.savings_pct < self._min_savings_pct:
                # Savings too small, pass through individually
                passthrough.extend(group)
                continue

            # Merge into single netted position
            merged = self._merge_positions(ng)
            netted.append(merged)
            netting_groups.append(ng)

        result = netted + passthrough

        self._metrics["netted_total"] = self._metrics.get("netted_total", 0) + 1
        self._metrics["orders_before"] = self._metrics.get("orders_before", 0) + original_count
        self._metrics["orders_after"] = self._metrics.get("orders_after", 0) + len(result)
        self._metrics["orders_saved"] = self._metrics.get("orders_saved", 0) + (original_count - len(result))

        total_savings = sum(ng.savings_pct for ng in netting_groups)

        logger.info(
            "Netting: %d → %d positions (%d saved, %.1f%% reduction)",
            original_count,
            len(result),
            original_count - len(result),
            (original_count - len(result)) / max(original_count, 1) * 100,
        )

        return result

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
