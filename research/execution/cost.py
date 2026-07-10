class TransactionCost:

    def __init__(self, commission, spread, slippage):
        self.commission = commission
        self.spread = spread
        self.slippage = slippage

    def calculate(self, order, price):
        commission_cost = self.commission.calculate(order.quantity)

        execution_price = self.spread.adjust_price(price, order.side)
        execution_price = self.slippage.adjust(execution_price, order.side)

        return {
            "price": execution_price,
            "cost": commission_cost
        }