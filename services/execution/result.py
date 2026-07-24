from dataclasses import dataclass


@dataclass
class ExecutionResult:

    order_id: str

    executed_quantity: float

    executed_price: float

    status: str