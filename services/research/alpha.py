"""
Alpha definition.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Alpha:

    alpha_id: str

    name: str

    description: str

    factor_id: str

    version: str

    created_at: datetime