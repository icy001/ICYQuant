"""Committee member data model for the Investment Committee Engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommitteeMember:
    """A member of the AI Investment Committee.

    Attributes:
        id: Unique identifier.
        role: Member role (e.g. "bull_analyst", "risk_manager").
        weight: Voting weight (0.0–1.0) based on expertise and accuracy.
    """

    id: str
    role: str
    weight: float
