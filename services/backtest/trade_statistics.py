"""
Trade statistics.
"""


class TradeStatistics:

    def calculate(
        self,
        trades,
    ):

        return {
            "trade_count":
                len(trades),
            "buy_count":
                len(
                    [
                        t
                        for t in trades
                        if t.side == "BUY"
                    ]
                ),
            "sell_count":
                len(
                    [
                        t
                        for t in trades
                        if t.side == "SELL"
                    ]
                ),
        }