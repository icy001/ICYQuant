"""
Research project states.
"""

from enum import Enum


class ProjectStatus(Enum):

    CREATED = "CREATED"

    ACTIVE = "ACTIVE"

    COMPLETED = "COMPLETED"

    ARCHIVED = "ARCHIVED"