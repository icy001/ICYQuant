"""
Scheduler job model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerJob:

    job_id: str

    job_type: str

    payload: dict