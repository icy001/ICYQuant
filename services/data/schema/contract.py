"""
Data contract.
"""

from dataclasses import dataclass
from .schema import DatasetSchema


@dataclass(frozen=True)
class DataContract:
    producer: str
    consumer: str
    schema: DatasetSchema