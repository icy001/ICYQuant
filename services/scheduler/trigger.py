from dataclasses import dataclass


@dataclass
class Trigger:

    trigger_id: str
    expression: str
