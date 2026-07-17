"""
Schema field definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaField:
    name: str
    dtype: str
    nullable: bool = False