from datetime import datetime
from typing import Optional, List, Dict, Callable

from research.data.bar import Bar
from research.data.provider import MarketDataProvider
from research.data.types import TimeFrame
from research.strategy.base import Strategy
from research.tradebook.tradebook import TradeBook

from .event import Event, BarEvent, SignalEvent, OrderEvent, FillEvent
from .queue import EventQueue
from .broker import BacktestBroker
from .context import BacktestContext
from .order import Order
from .fill import Fill


class BacktestEngine:
    def __init__(self):
        self.data_provider: Optional[MarketDataProvider] = None
        self.strategy: Optional[Strategy] = None
        self.context: Optional[BacktestContext] = None
        self.broker: Optional[BacktestBroker] = None
        self.queue: Optional[EventQueue] = None
        self.tradebook: Optional[TradeBook] = None
        self.handlers: Dict[type, List[Callable]] = {}
        self.results = {}
        self._bars: List[Bar] = []

    def setup(
        self,
        data_provider: MarketDataProvider,
        strategy: Strategy,
        symbol: str,
        initial_capital: float = 100000.0,
    ):
        self.data_provider = data_provider
        self.strategy = strategy
        self.context = BacktestContext(
            symbol=symbol,
            initial_capital=initial_capital,
            cash=initial_capital,
        )
        self.broker = BacktestBroker(self.context)
        self.queue = EventQueue()
        self.tradebook = TradeBook()
        
        self._register_handlers()
        self.strategy.initialize(self.context, self.broker, data_provider)

    def _register_handlers(self) -> None:
        self.register_handler(BarEvent, self._on_bar_event)
        self.register_handler(SignalEvent, self._on_signal_event)
        self.register_handler(OrderEvent, self._on_order_event)
        self.register_handler(FillEvent, self._on_fill_event)

    def register_handler(self, event_type: type, handler: Callable) -> None:
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    def _dispatch(self, event: Event) -> None:
        event_type = type(event)
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                handler(event)

    def _process_queue(self) -> None:
        while not self.queue.empty():
            event = self.queue.get()
            self._dispatch(event)

    def _on_bar_event(self, event: BarEvent) -> None:
        self.context.current_time = event.timestamp
        signal = self.strategy.on_bar(event.bar)
        
        if signal.signal_type != "HOLD":
            signal_event = SignalEvent(
                timestamp=event.timestamp,
                symbol=signal.symbol,
                side=signal.signal_type.value,
                quantity=self._calculate_quantity(signal, event.bar.close),
            )
            self.queue.publish(signal_event)
            self._process_queue()
        
        self._process_open_orders(event.bar)
        
        self.context.portfolio.update_equity_curve(
            timestamp=event.timestamp,
            prices={event.symbol: event.bar.close}
        )

    def _on_signal_event(self, event: SignalEvent) -> None:
        order = self.broker.submit_order(
            symbol=event.symbol,
            side=event.side,
            quantity=event.quantity,
        )
        
        order_event = OrderEvent(
            timestamp=event.timestamp,
            order_id=order.order_id,
            symbol=event.symbol,
            side=event.side,
            quantity=event.quantity,
        )
        self.queue.publish(order_event)

    def _on_order_event(self, event: OrderEvent) -> None:
        pass

    def _on_fill_event(self, event: FillEvent) -> None:
        self.strategy.on_fill(event)
        self.tradebook.record_trade(
            symbol=event.symbol,
            side=event.side,
            quantity=event.quantity,
            price=event.price,
            cash_change=event.cash_change,
            timestamp=event.timestamp,
            order_id=event.order_id,
        )
        self.context.portfolio.apply_fill(event)

    def _process_open_orders(self, bar: Bar) -> None:
        open_orders = [
            o for o in self.broker.get_all_orders().values() 
            if o.status == "SUBMITTED"
        ]
        for order in open_orders:
            fill = self.broker.execute_order(order, bar.close)
            if fill:
                fill_event = FillEvent(
                    timestamp=bar.timestamp,
                    fill_id=fill.fill_id,
                    order_id=fill.order_id,
                    symbol=fill.symbol,
                    side=fill.side,
                    quantity=fill.quantity,
                    price=fill.price,
                    cash_change=fill.cash_change,
                )
                self.queue.publish(fill_event)
                self._process_queue()

    def _calculate_quantity(self, signal, current_price: float) -> float:
        if signal.signal_type == "BUY":
            max_quantity = int(self.context.cash / (current_price * 1.001))
            return max_quantity * signal.strength
        elif signal.signal_type == "SELL":
            return self.context.get_position(signal.symbol) * signal.strength
        return 0.0

    def run(self, start: datetime, end: datetime, timeframe: TimeFrame = TimeFrame.D1):
        if not self.data_provider or not self.strategy or not self.context:
            raise ValueError("Engine not properly setup")

        self._bars = self.data_provider.load_bars(
            self.context.symbol, timeframe, start, end
        )
        
        self.strategy.on_start()

        for bar in self._bars:
            bar_event = BarEvent(
                timestamp=bar.timestamp,
                symbol=self.context.symbol,
                bar=bar,
            )
            self._dispatch(bar_event)

        self.strategy.on_finish()
        self._calculate_results()

        return self.results

    def _calculate_results(self):
        equity_curve = [eq for _, eq in self.context.portfolio.equity_curve]
        
        if equity_curve:
            final_value = equity_curve[-1]
            initial_value = self.context.initial_capital
            total_return = (final_value - initial_value) / initial_value

            max_drawdown = 0.0
            peak = equity_curve[0]
            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            sharpe_ratio = self._calculate_sharpe(equity_curve)
        else:
            final_value = self.context.cash
            initial_value = self.context.initial_capital
            total_return = 0.0
            max_drawdown = 0.0
            sharpe_ratio = 0.0

        self.results = {
            "start_date": self._bars[0].timestamp if self._bars else None,
            "end_date": self._bars[-1].timestamp if self._bars else None,
            "initial_capital": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "num_trades": len(self.tradebook.get_all_trades()),
            "sharpe_ratio": sharpe_ratio,
            "positions": dict(self.context.positions),
            "cash": self.context.cash,
            "equity_curve": self.context.portfolio.equity_curve,
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