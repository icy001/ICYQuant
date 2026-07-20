"""
Trade statistics.
"""


class TradeStatistics:
    def summarize(
        self,
        trades,
    ):
        return {
            "trade_count": len(trades),
        }