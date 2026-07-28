from dataclasses import dataclass


@dataclass
class Configuration:
    key: str
    value: str
    environment: str
    version: int