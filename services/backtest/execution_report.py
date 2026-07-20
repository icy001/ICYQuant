"""
Execution report.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionReport:
    order_id: str
    status: str
    filled_quantity: float