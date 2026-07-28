from dataclasses import dataclass


@dataclass
class RateLimitRule:

    resource: str
    limit: int
    window: int
