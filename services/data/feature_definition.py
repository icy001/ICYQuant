"""
Feature definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:

    feature_id: str

    name: str

    data_type: str

    description: str