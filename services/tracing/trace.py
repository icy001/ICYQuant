from dataclasses import dataclass


@dataclass
class Trace:

    trace_id: str
    operation: str
    status: str
