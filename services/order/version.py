"""
Order version value object.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    value: int = 1

    def next(self) -> "Version":
        return Version(self.value + 1)