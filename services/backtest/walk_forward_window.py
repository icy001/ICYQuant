"""
Walk-forward window model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WalkForwardWindow:

    train_start: datetime

    train_end: datetime

    test_start: datetime

    test_end: datetime