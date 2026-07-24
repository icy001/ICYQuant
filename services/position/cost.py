from dataclasses import dataclass


@dataclass
class CostBasis:

    position_id: str

    total_cost: float

    quantity: float