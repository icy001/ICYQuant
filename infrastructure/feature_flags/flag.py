"""
Feature flag definition.
"""


from dataclasses import dataclass


@dataclass
class FeatureFlag:

    name: str

    enabled: bool

    description: str