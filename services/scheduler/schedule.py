from dataclasses import dataclass


@dataclass
class Schedule:

    job_id: str
    trigger: "Trigger"
