from dataclasses import dataclass


@dataclass
class DiscoveryResult:
    service_name: str
    instances: list
