"""Trade Planning Assistant – generate trade execution plans."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TradePlan:
    """A structured trade execution plan.

    Contains entry price, stop loss, take-profit target, position size,
    and the rationale for the suggested action.
    """

    symbol: str
    action: str  # "buy", "sell", "hold"
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size: float = 0.0  # fraction of portfolio
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "rationale": self.rationale,
        }


class TradePlanner:
    """Generates trade plans based on signals, risk limits, and market context.

    Translates quantitative signals into actionable entries, stops, targets,
    and position sizes that a trader can review and execute.
    """

    def __init__(
        self,
        default_stop_pct: float = 0.05,
        default_target_pct: float = 0.15,
        default_position_size: float = 0.10,
    ):
        self.default_stop_pct = default_stop_pct
        self.default_target_pct = default_target_pct
        self.default_position_size = default_position_size

    def plan(
        self,
        symbol: str,
        current_price: float,
        signal: float,  # -1.0 to 1.0
        risk_limit: float = 1.0,
        strategy_name: str = "",
    ) -> TradePlan:
        """Generate a trade plan from a signal and current price."""
        # Determine action
        if signal > 0.3:
            action = "buy"
            direction = 1
        elif signal < -0.3:
            action = "sell"
            direction = -1
        else:
            return TradePlan(
                symbol=symbol,
                action="hold",
                entry_price=current_price,
                stop_loss=0.0,
                take_profit=0.0,
                position_size=0.0,
                rationale=f"Signal {signal:.2f} too weak; recommend holding.",
            )

        # Price levels
        stop_loss = current_price * (1 - direction * self.default_stop_pct)
        take_profit = current_price * (1 + direction * self.default_target_pct)

        # Position size scaled by signal strength and risk limit
        position_size = min(
            self.default_position_size * abs(signal),
            risk_limit,
        )

        rationale_parts = [
            f"{symbol}: {action.upper()} signal {signal:.2f}.",
            f"Entry @ {current_price:.2f}",
            f"Stop @ {stop_loss:.2f}",
            f"Target @ {take_profit:.2f}",
        ]
        if strategy_name:
            rationale_parts.insert(0, f"Strategy: {strategy_name}.")

        return TradePlan(
            symbol=symbol,
            action=action,
            entry_price=current_price,
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            position_size=round(position_size, 4),
            rationale=" ".join(rationale_parts),
        )
