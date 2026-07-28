from dataclasses import dataclass


@dataclass
class Failover:
    source_region: str
    target_region: str
    status: str
