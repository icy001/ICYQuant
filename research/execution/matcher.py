from typing import Optional

from .order import Order, OrderType
from .fill import Fill
from .commission import PerShareCommission
from .spread import FixedSpread
from .slippage import PercentageSlippage


class MatchingEngine:

    def __init__(self, commission_rate: float = 0.005, spread: float = 0.01, slippage_rate: float = 0.0005):
        self.commission_model = PerShareCommission(commission_rate)
        self.spread_model = FixedSpread(spread)
        self.slippage_model = PercentageSlippage(slippage_rate)

    def match(self, order: Order, market_price: float) -> Optional[Fill]:
        if order.order_type != OrderType.MARKET:
            return None

        if order.quantity <= 0:
            return None

        adjusted_price = self.spread_model.adjust_price(market_price, order.side.value)
        adjusted_price = self.slippage_model.adjust(adjusted_price, order.side.value)

        commission = self.commission_model.calculate(order.quantity)

        slippage_amount = abs(adjusted_price - market_price)

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            fill_price=adjusted_price,
            commission=commission,
            slippage=slippage_amount,
            side=order.side
        )

        return fill