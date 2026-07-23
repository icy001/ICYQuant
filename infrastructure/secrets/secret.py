from dataclasses import dataclass


@dataclass
class Secret:

    name: str

    value: str

    version: int = 1