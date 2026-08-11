"""Contract version management and compatibility checking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class VersionCompatibility(Enum):
    """Compatibility relationship between two contract versions."""

    COMPATIBLE = auto()
    INCOMPATIBLE = auto()
    DEPRECATED = auto()

    @property
    def label(self) -> str:
        _labels = {
            VersionCompatibility.COMPATIBLE: "COMPATIBLE",
            VersionCompatibility.INCOMPATIBLE: "INCOMPATIBLE",
            VersionCompatibility.DEPRECATED: "DEPRECATED",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def is_usable(self) -> bool:
        return self in (VersionCompatibility.COMPATIBLE, VersionCompatibility.DEPRECATED)


@dataclass
class ContractVersion:
    """Semantic version for control contracts.

    Format: MAJOR.MINOR (e.g. v1, v1.1, v2)
    A MAJOR bump means breaking changes; MINOR bump means backward-compatible additions.
    """

    major: int
    minor: int = 0

    @classmethod
    def parse(cls, version_str: str) -> "ContractVersion":
        """Parse a version string like 'v1', 'v1.1', '2', '3.0'."""
        raw = version_str.strip().lstrip("v").lstrip("V")
        parts = raw.split(".")
        major = int(parts[0]) if parts[0] else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        return cls(major=major, minor=minor)

    @classmethod
    def v1(cls) -> "ContractVersion":
        return cls(major=1, minor=0)

    @classmethod
    def v1_1(cls) -> "ContractVersion":
        return cls(major=1, minor=1)

    @classmethod
    def v2(cls) -> "ContractVersion":
        return cls(major=2, minor=0)

    def __str__(self) -> str:
        return f"v{self.major}" if self.minor == 0 else f"v{self.major}.{self.minor}"

    def __repr__(self) -> str:
        return f"ContractVersion({self})"

    def __hash__(self) -> int:
        return hash((self.major, self.minor))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContractVersion):
            return NotImplemented
        return self.major == other.major and self.minor == other.minor

    def __lt__(self, other: "ContractVersion") -> bool:
        return (self.major, self.minor) < (other.major, other.minor)

    def __le__(self, other: "ContractVersion") -> bool:
        return self == other or self < other


def check_compatibility(
    requested: ContractVersion,
    supported: ContractVersion,
) -> VersionCompatibility:
    """Determine compatibility between a requested version and the supported version.

    Rules:
      - Same major + same or higher minor → COMPATIBLE
      - Same major + lower minor → DEPRECATED (client is behind)
      - Different major → INCOMPATIBLE
    """
    if requested.major != supported.major:
        return VersionCompatibility.INCOMPATIBLE
    if supported.minor < requested.minor:
        # server version is behind what client asks → DEPRECATED
        return VersionCompatibility.DEPRECATED
    return VersionCompatibility.COMPATIBLE
