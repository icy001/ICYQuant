from typing import List, Optional
from datetime import datetime

from .trade import Trade


class TradeJournal:
    def __init__(self):
        self._trades: List[Trade] = []
        self._trade_id_counter = 0

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        strategy: str,
        time: datetime,
    ) -> Trade:
        self._trade_id_counter += 1
        trade_id = f"trade_{self._trade_id_counter:06d}"

        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            strategy=strategy,
            time=time,
        )

        self._trades.append(trade)
        return trade

    def close_trade(self, trade_id: str, exit_price: float) -> Optional[Trade]:
        for trade in self._trades:
            if trade.trade_id == trade_id:
                trade.exit_price = exit_price
                trade.pnl = (exit_price - trade.entry_price) * trade.quantity
                return trade
        return None

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        for trade in self._trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    def get_all_trades(self) -> List[Trade]:
        return list(self._trades)

    def get_trades_by_symbol(self, symbol: str) -> List[Trade]:
        return [trade for trade in self._trades if trade.symbol == symbol]

    def get_trades_by_strategy(self, strategy: str) -> List[Trade]:
        return [trade for trade in self._trades if trade.strategy == strategy]

    def get_open_trades(self) -> List[Trade]:
        return [trade for trade in self._trades if trade.exit_price is None]

    def get_closed_trades(self) -> List[Trade]:
        return [trade for trade in self._trades if trade.exit_price is not None]

    def get_total_pnl(self) -> float:
        return sum(trade.pnl or 0 for trade in self._trades)

    def get_win_rate(self) -> float:
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return 0.0
        winning_trades = sum(1 for trade in closed_trades if trade.pnl and trade.pnl > 0)
        return winning_trades / len(closed_trades)