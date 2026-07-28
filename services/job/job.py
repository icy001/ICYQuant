from dataclasses import dataclass


@dataclass
class Job:

    job_id: str
    name: str
    status: str
    priority: str
