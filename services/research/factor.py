"""
Factor definition.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Factor:

    factor_id: str

    name: str

    expression: str

    version: str

    created_at: datetime