from dataclasses import dataclass


@dataclass
class LedgerEntry:
    entry_id: str
    account_id: str
    amount: float
    currency: str
    direction: str