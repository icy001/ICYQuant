from enum import Enum
from os import getenv


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


def get_trading_mode() -> TradingMode:
    mode = getenv("ICYQUANT_MODE", "PAPER").upper()
    return TradingMode(mode)