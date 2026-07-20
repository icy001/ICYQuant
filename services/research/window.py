"""
Walk-forward window.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str