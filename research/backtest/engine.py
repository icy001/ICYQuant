from datetime import datetime
from typing import Optional

from research.data.provider import MarketDataProvider
from research.strategy.base import Strategy
from research.strategy.context import StrategyContext
from research.tradebook.tradebook import TradeBook

from .broker import BacktestBroker, Order, Fill


class BacktestEngine:
    def __init__(self):
        self.data_provider: Optional[MarketDataProvider] = None
        self.strategy: Optional[Strategy] = None
        self.context: Optional[StrategyContext] = None
        self.broker: Optional[BacktestBroker] = None
        self.tradebook: Optional[TradeBook] = None
        self.results = {}

    def setup(
        self,
        data_provider: MarketDataProvider,
        strategy: Strategy,
        symbol: str,
        initial_capital: float = 100000.0,
    ):
        self.data_provider = data_provider
        self.strategy = strategy
        self.context = StrategyContext(
            symbol=symbol,
            initial_capital=initial_capital,
            cash=initial_capital,
        )
        self.broker = BacktestBroker(self.context)
        self.tradebook = TradeBook()
        self.strategy.initialize(self.context, self.broker, data_provider)

    def run(self, start: datetime, end: datetime, timeframe: str = "1D"):
        if not self.data_provider or not self.strategy or not self.context:
            raise ValueError("Engine not properly setup")

        bars = self.data_provider.load_bars(self.context.symbol, start, end, timeframe)
        
        self.strategy.on_start()

        for idx, bar in bars.iterrows():
            self.context.current_time = idx
            
            self.strategy.on_bar(bar)

            open_orders = [o for o in self.broker.get_all_orders().values() if o.status == "SUBMITTED"]
            for order in open_orders:
                fill = self.broker.execute_order(order, bar["close"])
                if fill:
                    self.strategy.on_fill(fill)
                    self.tradebook.record_trade(
                        symbol=fill.symbol,
                        side=fill.side,
                        quantity=fill.quantity,
                        price=fill.price,
                        cash_change=fill.cash_change,
                        timestamp=idx,
                        order_id=fill.order_id,
                    )

        self.strategy.on_finish()
        self._calculate_results(bars)

        return self.results

    def _calculate_results(self, bars):
        final_value = self.context.cash
        for symbol, qty in self.context.positions.items():
            if qty > 0 and "close" in bars.columns:
                final_value += qty * bars["close"].iloc[-1]

        initial_value = self.context.initial_capital
        total_return = (final_value - initial_value) / initial_value

        equity_curve = []
        cash = self.context.initial_capital
        positions = {}
        
        for idx, bar in bars.iterrows():
            for symbol, qty in positions.items():
                cash += qty * bar["close"]
            equity_curve.append(cash)
            positions = dict(self.context.positions)

        max_drawdown = 0.0
        peak = equity_curve[0]
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        self.results = {
            "start_date": bars.index[0],
            "end_date": bars.index[-1],
            "initial_capital": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "num_trades": len(self.tradebook.get_all_trades()),
            "sharpe_ratio": self._calculate_sharpe(equity_curve),
            "positions": dict(self.context.positions),
            "cash": self.context.cash,
        }

    def _calculate_sharpe(self, equity_curve) -> float:
        if len(equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(equity_curve)):
            returns.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])
        
        if not returns:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
        
        if std_return == 0:
            return 0.0
        
        return mean_return / std_return * (252 ** 0.5)

    def get_results(self):
        return self.results

    def get_tradebook(self):
        return self.tradebook