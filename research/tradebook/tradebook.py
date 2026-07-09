from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    cash_change: float
    timestamp: datetime
    order_id: Optional[str] = None
    reason: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None
    strategy_version: Optional[str] = None
    market_environment: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class DailySummary:
    date: datetime
    total_trades: int = 0
    total_pnl: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0


class TradeBook:
    def __init__(self):
        self._trades: List[TradeRecord] = []
        self._trade_id_counter = 0

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        cash_change: float,
        timestamp: datetime,
        order_id: Optional[str] = None,
        reason: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        notes: Optional[str] = None,
        strategy_version: Optional[str] = None,
        market_environment: Optional[str] = None,
    ) -> TradeRecord:
        self._trade_id_counter += 1
        trade_id = f"trade_{self._trade_id_counter:06d}"

        trade = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            cash_change=cash_change,
            timestamp=timestamp,
            order_id=order_id,
            reason=reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notes=notes,
            strategy_version=strategy_version,
            market_environment=market_environment,
        )

        self._trades.append(trade)
        return trade

    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        for trade in self._trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    def get_all_trades(self) -> List[TradeRecord]:
        return list(self._trades)

    def get_trades_by_symbol(self, symbol: str) -> List[TradeRecord]:
        return [trade for trade in self._trades if trade.symbol == symbol]

    def get_trades_by_date(self, date: datetime) -> List[TradeRecord]:
        return [trade for trade in self._trades if trade.timestamp.date() == date.date()]

    def get_trades_by_side(self, side: str) -> List[TradeRecord]:
        return [trade for trade in self._trades if trade.side == side]

    def get_daily_summary(self, date: datetime) -> DailySummary:
        trades = self.get_trades_by_date(date)
        
        summary = DailySummary(date=date)
        summary.total_trades = len(trades)

        if not trades:
            return summary

        wins = []
        losses = []

        for trade in trades:
            pnl = trade.cash_change
            summary.total_pnl += pnl

            if pnl > 0:
                wins.append(pnl)
            else:
                losses.append(pnl)

        summary.winning_trades = len(wins)
        summary.losing_trades = len(losses)
        
        if wins:
            summary.avg_win = sum(wins) / len(wins)
            summary.max_win = max(wins)
        
        if losses:
            summary.avg_loss = sum(losses) / len(losses)
            summary.max_loss = min(losses)

        return summary

    def get_total_summary(self) -> DailySummary:
        if not self._trades:
            return DailySummary(date=datetime.now())

        summary = DailySummary(date=self._trades[0].timestamp)
        summary.total_trades = len(self._trades)

        wins = []
        losses = []

        for trade in self._trades:
            pnl = trade.cash_change
            summary.total_pnl += pnl

            if pnl > 0:
                wins.append(pnl)
            else:
                losses.append(pnl)

        summary.winning_trades = len(wins)
        summary.losing_trades = len(losses)
        
        if wins:
            summary.avg_win = sum(wins) / len(wins)
            summary.max_win = max(wins)
        
        if losses:
            summary.avg_loss = sum(losses) / len(losses)
            summary.max_loss = min(losses)

        return summary

    def generate_trade_report(self) -> str:
        summary = self.get_total_summary()
        trades = self.get_all_trades()

        report = []
        report.append("=" * 60)
        report.append("ICYQuant Trade Report")
        report.append("=" * 60)
        report.append(f"Total Trades: {summary.total_trades}")
        report.append(f"Winning Trades: {summary.winning_trades}")
        report.append(f"Losing Trades: {summary.losing_trades}")
        report.append(f"Win Rate: {(summary.winning_trades / summary.total_trades * 100):.1f}%" if summary.total_trades > 0 else "Win Rate: N/A")
        report.append(f"Total PnL: ${summary.total_pnl:,.2f}")
        report.append(f"Average Win: ${summary.avg_win:,.2f}" if summary.winning_trades > 0 else "Average Win: N/A")
        report.append(f"Average Loss: ${summary.avg_loss:,.2f}" if summary.losing_trades > 0 else "Average Loss: N/A")
        report.append(f"Max Win: ${summary.max_win:,.2f}" if summary.winning_trades > 0 else "Max Win: N/A")
        report.append(f"Max Loss: ${summary.max_loss:,.2f}" if summary.losing_trades > 0 else "Max Loss: N/A")
        report.append("-" * 60)
        report.append("Trade Details:")
        report.append("-" * 60)

        for trade in trades:
            pnl = -trade.cash_change if trade.side == "BUY" else trade.cash_change
            report.append(f"\nTrade {trade.trade_id}:")
            report.append(f"  Symbol: {trade.symbol}")
            report.append(f"  Side: {trade.side}")
            report.append(f"  Quantity: {trade.quantity}")
            report.append(f"  Price: ${trade.price:.2f}")
            report.append(f"  PnL: ${pnl:,.2f}")
            report.append(f"  Timestamp: {trade.timestamp}")
            if trade.reason:
                report.append(f"  Reason: {trade.reason}")
            if trade.notes:
                report.append(f"  Notes: {trade.notes}")

        report.append("=" * 60)
        return "\n".join(report)