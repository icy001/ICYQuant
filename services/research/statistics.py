"""
Trade statistics.
"""


class TradeStatistics:
    def win_rate(
        self,
        wins: int,
        total: int,
    ) -> float:
        if total == 0:
            return 0.0
        return wins / total