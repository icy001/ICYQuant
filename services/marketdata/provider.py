class MarketDataProvider:

    def subscribe(
        self,
        symbol
    ):
        raise NotImplementedError

    def history(
        self,
        symbol
    ):
        raise NotImplementedError