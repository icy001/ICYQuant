from dataclasses import dataclass


@dataclass
class RolloutRule:

    percentage: int
    target_group: str
