from dataclasses import dataclass


@dataclass
class FailureRecord:
    service_name: str
    error_count: int
    last_error_time: int
