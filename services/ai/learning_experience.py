"""
Learning experience model.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class LearningExperience:

    timestamp: datetime

    source: str

    input_data: Any

    output_data: Any

    reward: float

    metadata: dict