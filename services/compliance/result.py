from dataclasses import dataclass


@dataclass
class ComplianceResult:
    passed: bool
    reason: str = ""