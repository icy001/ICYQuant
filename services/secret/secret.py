from dataclasses import dataclass


@dataclass
class Secret:
    secret_id: str
    name: str
    value: str
    secret_type: str