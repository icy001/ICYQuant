"""
Dataset definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dataset:
    dataset_id: str = ""
    name: str = ""
    description: str = ""
    schema: dict = None
    source_id: str = ""

    def __post_init__(self):
        if self.schema is None:
            object.__setattr__(self, "schema", {})