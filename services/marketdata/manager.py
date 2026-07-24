class MarketDataManager:

    def __init__(
        self,
        provider,
        cache
    ):
        self.provider = provider
        self.cache = cache

    def get_quote(
        self,
        symbol
    ):
        quote = self.provider.subscribe(
            symbol
        )

        self.cache.set(
            symbol,
            quote
        )

        return quote