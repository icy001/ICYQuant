"""
Feature definition.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Feature:

    feature_id: str

    name: str

    data_type: str

    description: str

    version: str

    created_at: datetime