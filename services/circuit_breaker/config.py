from dataclasses import dataclass


@dataclass
class CircuitConfig:
    failure_threshold: int
    recovery_timeout: int
