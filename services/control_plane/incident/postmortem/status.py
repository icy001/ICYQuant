"""PostmortemStatus — lifecycle of an incident postmortem."""

from enum import Enum


class PostmortemStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
