from dataclasses import dataclass


@dataclass
class PnL:
    account_id: str
    realized: float
    unrealized: float

    def total(self):
        return self.realized + self.unrealized