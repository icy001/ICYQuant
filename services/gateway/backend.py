from dataclasses import dataclass


@dataclass
class BackendInstance:
    host: str
    port: int
    healthy: bool = True
