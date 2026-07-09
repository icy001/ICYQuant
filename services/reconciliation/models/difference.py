from dataclasses import dataclass
from typing import Any

from .types import DifferenceType


@dataclass
class Difference:
    diff_type: DifferenceType
    entity_id: str
    expected: Any
    actual: Any
    message: str = ""
