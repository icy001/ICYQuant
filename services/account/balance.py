from dataclasses import dataclass


@dataclass
class Balance:

    account_id: str

    currency: str

    amount: float