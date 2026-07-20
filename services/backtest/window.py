"""
Walk forward window.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisWindow:
    training_start: str
    training_end: str
    validation_start: str
    validation_end: str