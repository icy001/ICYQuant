"""
Ledger account.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import AccountType


class LedgerDirection:
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass
class LedgerAccount:
    code: str
    name: str
    account_type: AccountType