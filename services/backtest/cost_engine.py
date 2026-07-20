"""
Transaction cost engine.
"""


class TransactionCostEngine:
    def __init__(
        self,
        commission,
        slippage,
        spread,
    ):
        self.commission = commission
        self.slippage = slippage
        self.spread = spread

    def calculate(
        self,
        order,
        price,
    ):
        commission = self.commission.calculate(order.quantity, price)
        adjusted_price = self.slippage.calculate(price, order.side)
        spread = self.spread.calculate(price)

        return {
            "commission": commission,
            "price": adjusted_price,
            "spread": spread,
        }