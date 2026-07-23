"""
Trading context memory.
"""


class TradingContextMemory:

    def __init__(
        self,
    ):

        self._contexts = {}

    def update(
        self,
        strategy_id,
        context,
    ):

        self._contexts[
            strategy_id
        ] = context

    def get(
        self,
        strategy_id,
    ):

        return self._contexts.get(
            strategy_id,
        )