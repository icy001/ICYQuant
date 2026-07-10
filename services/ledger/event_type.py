"""
Ledger event type definitions.

Every state change inside ICYQuant
must be represented as an immutable event.
"""

from enum import Enum


class LedgerEventType(str, Enum):
    """
    Supported ledger events.
    """

    ACCOUNT_CREATED = "ACCOUNT_CREATED"

    CASH_DEPOSITED = "CASH_DEPOSITED"
    CASH_WITHDRAWN = "CASH_WITHDRAWN"

    ORDER_CREATED = "ORDER_CREATED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"

    ORDER_FILLED = "ORDER_FILLED"

    COMMISSION_CHARGED = "COMMISSION_CHARGED"

    POSITION_ADJUSTED = "POSITION_ADJUSTED"

    MARKET_PRICE_UPDATED = "MARKET_PRICE_UPDATED"

    DIVIDEND_RECEIVED = "DIVIDEND_RECEIVED"

    FEE_CHARGED = "FEE_CHARGED"

    SYSTEM_ADJUSTMENT = "SYSTEM_ADJUSTMENT"