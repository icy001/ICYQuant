"""
Pipeline execution record.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionRecord:
    pipeline_id: str
    status: str
    started_at: str