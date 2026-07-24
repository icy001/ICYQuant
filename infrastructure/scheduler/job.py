from dataclasses import dataclass


@dataclass
class Job:

    name: str

    task: str

    status: str = "READY"