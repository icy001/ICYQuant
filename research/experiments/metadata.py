from dataclasses import dataclass
from datetime import date
from typing import Dict


@dataclass(frozen=True)
class ExperimentMetadata:
    name: str
    strategy: str
    symbols: list[str]
    start: date
    end: date
    parameters: Dict = None