"""
Exposure limit model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExposureLimit:

    asset: str

    max_exposure: float