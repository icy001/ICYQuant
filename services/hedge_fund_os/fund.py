"""Fund entity data model for the Hedge Fund Operating System."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fund:
    """A hedge fund entity managed by the AI Fund Operating System.

    Attributes:
        id: Unique fund identifier.
        name: Fund display name.
        strategy: Investment strategy label (e.g. "long_short", "market_neutral").
    """

    id: str
    name: str
    strategy: str
