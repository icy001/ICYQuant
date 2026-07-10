"""
Conflict resolution engine.
"""

from __future__ import annotations


from .policy import (
    ResolutionPolicy,
    ResolutionAction,
)


class ConflictResolutionEngine:
    """
    Determines how conflicts
    should be handled.
    """

    def __init__(
        self,
        policy=None,
    ):
        self.policy = (
            policy
            or
            ResolutionPolicy()
        )

    def resolve(
        self,
        sources: dict,
    ) -> ResolutionAction:
        return self.policy.decide(
            sources
        )