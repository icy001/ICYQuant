"""
Service response model.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceResponse:

    success: bool

    data: dict

    error: Optional[str] = None