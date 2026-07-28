from dataclasses import dataclass


@dataclass
class CacheEntry:

    key: str
    value: object
    ttl: int
