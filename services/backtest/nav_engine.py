"""
Net asset value engine.
"""


class NavEngine:

    def calculate(
        self,
        cash,
        market_value,
    ):

        equity = cash + market_value

        return {
            "equity": equity,
            "nav": equity,
        }