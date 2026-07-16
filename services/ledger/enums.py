"""
Ledger enums.
"""

from __future__ import annotations

from enum import Enum


class EntrySide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"