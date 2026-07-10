class MarketDataError(Exception):
    pass


class SymbolNotFoundError(MarketDataError):
    pass


class InvalidTimeframeError(MarketDataError):
    pass


class DataLoadError(MarketDataError):
    pass


class DataFormatError(MarketDataError):
    pass