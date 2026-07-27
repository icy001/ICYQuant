from dataclasses import dataclass


@dataclass
class ComplianceRule:
    rule_id: str
    name: str
    enabled: bool = True
    description: str = ""