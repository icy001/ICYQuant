class MarketDataService:

    def __init__(
        self,
        manager
    ):
        self.manager = manager

    def quote(
        self,
        symbol
    ):
        return self.manager.get_quote(
            symbol
        )