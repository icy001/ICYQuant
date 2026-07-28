from dataclasses import dataclass


@dataclass
class LockRequest:
    resource: str
    owner: str
