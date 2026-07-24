from dataclasses import dataclass


@dataclass
class Account:

    account_id: str

    user_id: str

    account_type: str

    status: str = "ACTIVE"