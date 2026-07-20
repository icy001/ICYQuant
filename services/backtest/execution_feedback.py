"""
Execution feedback.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionFeedback:
    order_id: str
    status: str