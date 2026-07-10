"""
Conflict resolution policies.

Defines trust rules between
different state sources.
"""

from __future__ import annotations


from enum import Enum


class DataSource(str, Enum):
    BROKER = "BROKER"

    LEDGER = "LEDGER"

    MANUAL = "MANUAL"


class ResolutionAction(str, Enum):
    AUTO_REPAIR = (
        "AUTO_REPAIR"
    )

    REQUIRE_APPROVAL = (
        "REQUIRE_APPROVAL"
    )

    IGNORE = (
        "IGNORE"
    )


class ResolutionPolicy:
    """
    Source priority rules.

    Higher priority wins.
    """

    PRIORITY = {
        DataSource.BROKER:
            100,
        DataSource.LEDGER:
            80,
        DataSource.MANUAL:
            50,
    }

    def decide(
        self,
        sources: dict,
    ) -> ResolutionAction:
        if len(sources) <= 1:
            return (
                ResolutionAction.IGNORE
            )

        values = list(
            sources.values()
        )

        if len(
            set(values)
        ) == 1:
            return (
                ResolutionAction.IGNORE
            )

        return (
            ResolutionAction.REQUIRE_APPROVAL
        )