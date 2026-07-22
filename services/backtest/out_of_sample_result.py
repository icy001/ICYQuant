"""
Out-of-sample result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OutOfSampleResult:

    parameters: dict

    performance: dict