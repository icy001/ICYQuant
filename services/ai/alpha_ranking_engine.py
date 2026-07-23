"""
Alpha ranking engine.
"""


class AlphaRankingEngine:

    def rank(
        self,
        candidates,
    ):

        return sorted(
            candidates,
            key=lambda x: x.sharpe,
            reverse=True,
        )