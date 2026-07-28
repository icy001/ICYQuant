from dataclasses import dataclass


@dataclass
class AuditMetadata:
    timestamp: str
    source: str
    ip: str
