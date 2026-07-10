from typing import Dict, List, Optional
from datetime import datetime

from research.backtest.timeline import Timeline
from research.backtest.simulator import SimulatedBroker, Fill
from research.portfolio.portfolio import Portfolio
from research.strategy.base import Strategy
from research.data.provider import MarketDataProvider
from research.data.types import TimeFrame
from research.data.bar import Bar
from research.strategy.signal import Signal
from research.analytics.report import PerformanceReport
from research.tradebook.journal import TradeJournal


class MultiAssetBacktestEngine:
    def __init__(
        self,
        data_provider: MarketDataProvider,
        strategy: Strategy,
        symbols: List[str],
        initial_capital: float = 100000.0,
    ):
        self.data_provider = data_provider
        self.strategy = strategy
        self.symbols = symbols
        self.initial_capital = initial_capital
        self.broker = SimulatedBroker()
        self.portfolio = Portfolio(initial_cash=initial_capital)
        self.trade_journal = TradeJournal()
        self.timeline = Timeline()
        self._prices: Dict[str, float] = {}

    def _load_market_data(self, start: Optional[datetime], end: Optional[datetime], timeframe: TimeFrame) -> None:
        datasets = {}
        for symbol in self.symbols:
            bars = self.data_provider.load_bars(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            datasets[symbol] = bars
        self.timeline.merge(datasets)

    def _execute_signal(self, signal: Signal, timestamp: datetime) -> None:
        if signal.signal_type.value == "HOLD":
            return
        
        price = self._prices.get(signal.symbol, 0.0)
        if price <= 0:
            return
        
        fill = self.broker.execute(signal, price)
        
        if fill:
            self.portfolio.apply_fill(fill)
            
            self.trade_journal.record_trade(
                symbol=fill.symbol,
                entry_price=fill.price,
                quantity=fill.quantity,
                strategy=self.strategy.__class__.__name__,
                time=timestamp,
            )

    def run(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> PerformanceReport:
        self._load_market_data(start, end, timeframe)

        for timestamp, market_data in self.timeline:
            for symbol, bar in market_data.items():
                self._prices[symbol] = bar.close
            
            signals = self.strategy.on_market(market_data)
            
            if isinstance(signals, Signal):
                signals = [signals]
            
            for signal in signals:
                self._execute_signal(signal, timestamp)
            
            self.portfolio.update_equity_curve(timestamp, self._prices)

        return PerformanceReport.generate(
            symbol=", ".join(self.symbols),
            strategy_name=self.strategy.__class__.__name__,
            initial_capital=self.initial_capital,
            equity_curve=self.portfolio.equity_curve,
            num_trades=len(self.trade_journal.get_all_trades()),
            win_rate=self.trade_journal.get_win_rate(),
        )