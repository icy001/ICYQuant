from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    RISK_CHECK = "RISK_CHECK"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"