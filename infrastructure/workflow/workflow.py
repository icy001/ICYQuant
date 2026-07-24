from dataclasses import dataclass


@dataclass
class Workflow:

    name: str

    status: str = "CREATED"