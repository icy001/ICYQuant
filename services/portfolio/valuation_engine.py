"""
Portfolio valuation engine.
"""


class ValuationEngine:
    def __init__(
        self,
        pnl_calculator,
        nav_calculator,
    ):
        self.pnl_calculator = pnl_calculator
        self.nav_calculator = nav_calculator

    def calculate(
        self,
        positions,
        prices,
        cash,
    ):
        results = []

        for position in positions:
            price = prices[position.symbol]
            market_value = position.quantity * price
            pnl = self.pnl_calculator.unrealized(position.quantity, position.average_price, price)

            results.append({
                "symbol": position.symbol,
                "market_value": market_value,
                "unrealized_pnl": pnl,
            })

        nav = self.nav_calculator.calculate(
            [type("Value", (), {"market_value": item["market_value"]}) for item in results],
            cash,
        )

        return {
            "positions": results,
            "nav": nav,
        }