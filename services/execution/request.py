from dataclasses import dataclass


@dataclass
class ExecutionRequest:

    order_id: str

    symbol: str

    quantity: float

    side: str

    order_type: str