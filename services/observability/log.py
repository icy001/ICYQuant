from dataclasses import dataclass


@dataclass
class LogEvent:

    level: str

    message: str

    service: str
