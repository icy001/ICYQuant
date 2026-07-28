from dataclasses import dataclass


@dataclass
class ConfigVersion:
    key: str
    version: int
    timestamp: int