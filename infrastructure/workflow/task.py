from dataclasses import dataclass


@dataclass
class Task:

    name: str

    action: str

    status: str = "PENDING"