from typing import Optional
from datetime import datetime

from research.backtest.simulator import SimulatedBroker, Fill
from research.portfolio.portfolio import Portfolio
from research.strategy.base import Strategy
from research.data.provider import MarketDataProvider
from research.data.types import TimeFrame
from research.analytics.report import PerformanceReport
from research.tradebook.journal import TradeJournal


class BacktestRunner:
    def __init__(
        self,
        data_provider: MarketDataProvider,
        strategy: Strategy,
        symbol: str,
        initial_capital: float = 100000.0,
    ):
        self.data_provider = data_provider
        self.strategy = strategy
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.broker = SimulatedBroker()
        self.portfolio = Portfolio(initial_cash=initial_capital)
        self.trade_journal = TradeJournal()

    def run(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> PerformanceReport:
        bars = self.data_provider.load_bars(
            symbol=self.symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )

        for bar in bars:
            signal = self.strategy.on_bar(bar)
            
            if signal.signal_type.value != "HOLD":
                fill = self.broker.execute(signal, bar.close)
                
                if fill:
                    self.portfolio.apply_fill(fill)
                    
                    self.trade_journal.record_trade(
                        symbol=fill.symbol,
                        entry_price=fill.price,
                        quantity=fill.quantity,
                        strategy=self.strategy.__class__.__name__,
                        time=bar.timestamp,
                    )
            
            self.portfolio.update_equity_curve(
                timestamp=bar.timestamp,
                prices={self.symbol: bar.close},
            )

        return PerformanceReport.generate(
            symbol=self.symbol,
            strategy_name=self.strategy.__class__.__name__,
            initial_capital=self.initial_capital,
            equity_curve=self.portfolio.equity_curve,
            num_trades=len(self.trade_journal.get_all_trades()),
            win_rate=self.trade_journal.get_win_rate(),
        )