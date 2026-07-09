from enum import Enum


class DifferenceType(str, Enum):
    POSITION = "POSITION"
    CASH = "CASH"
    ORDER = "ORDER"
    TRADE = "TRADE"
    ACCOUNT = "ACCOUNT"
