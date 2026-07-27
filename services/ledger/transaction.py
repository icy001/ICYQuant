from dataclasses import dataclass


@dataclass
class Transaction:
    transaction_id: str
    description: str
    entries: list