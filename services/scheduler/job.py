from dataclasses import dataclass


@dataclass
class Job:

    job_id: str
    name: str
    task: str
    status: str
