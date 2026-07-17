"""
Feature version.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureVersion:
    feature_name: str
    version: str