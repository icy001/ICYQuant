"""
Factor definition.
"""

from dataclasses import dataclass


@dataclass
class Factor:

    name: str

    category: str

    formula: str