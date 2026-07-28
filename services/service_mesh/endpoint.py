from dataclasses import dataclass


@dataclass
class ServiceEndpoint:

    name: str
    host: str
    port: int
    healthy: bool = True
