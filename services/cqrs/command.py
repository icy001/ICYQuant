from dataclasses import dataclass


@dataclass
class Command:
    command_id: str
    command_type: str
    payload: dict
