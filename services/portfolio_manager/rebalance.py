"""Dynamic Rebalancing Engine – intelligent portfolio drift correction."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RebalanceOrder:
    """A single rebalance trade order."""

    symbol: str
    action: str  # "buy", "sell", "hold"
    current_weight: float
    target_weight: float
    delta: float  # positive = buy, negative = sell
    size: float = 0.0  # notional value
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
            "delta": self.delta,
            "size": self.size,
            "reason": self.reason,
        }


@dataclass
class RebalanceResult:
    """Result of a rebalancing operation."""

    status: str  # "rebalanced", "no_action", "partial", "skipped"
    orders: List[RebalanceOrder] = field(default_factory=list)
    turnover: float = 0.0
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "orders": [o.to_dict() for o in self.orders],
            "turnover": self.turnover,
            "message": self.message,
        }


class RebalanceEngine:
    """Generates rebalance orders to align portfolio weights with targets.

    Handles drift-based triggers, signal change triggers, risk increase
    triggers, and market regime change triggers. Respects turnover limits.
    """

    def __init__(
        self,
        drift_threshold: float = 0.03,
        min_trade_size: float = 0.005,
        turnover_limit: float = 0.30,
    ):
        self.drift_threshold = drift_threshold
        self.min_trade_size = min_trade_size
        self.turnover_limit = turnover_limit

    def rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        total_value: float = 1_000_000.0,
        force: bool = False,
    ) -> RebalanceResult:
        """Compute rebalance orders from current to target weights.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Desired portfolio weights.
            total_value: Total portfolio value for sizing.
            force: If True, rebalance regardless of drift threshold.
        """
        orders: List[RebalanceOrder] = []
        all_symbols = set(current_weights.keys()) | set(target_weights.keys())

        for symbol in all_symbols:
            curr = current_weights.get(symbol, 0.0)
            tgt = target_weights.get(symbol, 0.0)
            delta = tgt - curr

            if abs(delta) < self.min_trade_size and not force:
                orders.append(RebalanceOrder(
                    symbol=symbol,
                    action="hold",
                    current_weight=curr,
                    target_weight=tgt,
                    delta=0.0,
                    reason="Within tolerance",
                ))
                continue

            if abs(delta) < self.drift_threshold and not force:
                orders.append(RebalanceOrder(
                    symbol=symbol,
                    action="hold",
                    current_weight=curr,
                    target_weight=tgt,
                    delta=delta,
                    reason="Drift below threshold",
                ))
                continue

            action = "buy" if delta > 0 else "sell"
            size = abs(delta) * total_value
            orders.append(RebalanceOrder(
                symbol=symbol,
                action=action,
                current_weight=curr,
                target_weight=tgt,
                delta=round(delta, 4),
                size=round(size, 2),
                reason=f"Rebalance {'toward' if delta > 0 else 'away from'} target",
            ))

        # Calculate turnover (sum of absolute deltas / 2)
        turnover = sum(abs(o.delta) for o in orders) / 2.0

        # Check turnover limit
        if turnover > self.turnover_limit and not force:
            return RebalanceResult(
                status="skipped",
                orders=orders,
                turnover=turnover,
                message=f"Turnover {turnover:.1%} exceeds limit {self.turnover_limit:.1%}",
            )

        # Determine status
        trades = [o for o in orders if o.action != "hold"]
        if not trades:
            return RebalanceResult(
                status="no_action",
                orders=orders,
                turnover=0.0,
                message="Portfolio already at target weights.",
            )

        return RebalanceResult(
            status="rebalanced",
            orders=orders,
            turnover=round(turnover, 4),
            message=f"Generated {len(trades)} trades, turnover {turnover:.2%}.",
        )

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        signal_change: bool = False,
        risk_increase: bool = False,
        regime_change: bool = False,
    ) -> bool:
        """Determine whether rebalancing should be triggered.

        Returns True if any trigger condition is met:
        - Weight drift exceeds threshold
        - Significant signal change
        - Risk level has increased
        - Market regime has shifted
        """
        if signal_change or risk_increase or regime_change:
            return True

        all_symbols = set(current_weights.keys()) | set(target_weights.keys())
        for symbol in all_symbols:
            curr = current_weights.get(symbol, 0.0)
            tgt = target_weights.get(symbol, 0.0)
            if abs(curr - tgt) > self.drift_threshold:
                return True

        return False
