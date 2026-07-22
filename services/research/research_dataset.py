"""
Research dataset model.
"""

from dataclasses import dataclass


@dataclass
class ResearchDataset:

    dataset_id: str

    name: str

    source: str

    schema: dict