from dataclasses import dataclass


@dataclass
class ServiceHealth:
    service_name: str
    status: str
    latency: float