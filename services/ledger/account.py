"""
Ledger account.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import AccountType


@dataclass
class LedgerAccount:
    code: str
    name: str
    account_type: AccountType