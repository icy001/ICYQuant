"""Factor definition (moved from services/research/factor.py, which was
shadowed by the factor/ package and therefore unreachable)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Factor:

    factor_id: str

    name: str

    expression: str

    version: str

    created_at: datetime
