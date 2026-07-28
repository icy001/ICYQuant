from dataclasses import dataclass


@dataclass
class AllocationRequest:
    portfolio_id: str
    assets: list