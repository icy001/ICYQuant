"""
Feature metadata.
"""

from dataclasses import dataclass


@dataclass
class FeatureMetadata:

    owner: str

    category: str

    tags: list[str]

    source: str

    frequency: str