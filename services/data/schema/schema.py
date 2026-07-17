"""
Dataset schema model.
"""

from dataclasses import dataclass
from .field import SchemaField


@dataclass(frozen=True)
class DatasetSchema:
    name: str
    version: str
    fields: list[SchemaField]