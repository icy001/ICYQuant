from dataclasses import dataclass


@dataclass
class Route:
    path: str
    service_name: str
