"""
Market data source definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSource:

    source_id: str

    name: str

    provider: str

    description: str