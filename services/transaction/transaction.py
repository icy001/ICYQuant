from dataclasses import dataclass


@dataclass
class Transaction:

    transaction_id: str
    status: str
    business_type: str
