"""
IncidentFingerprint — stable deduplication key for recurring failures.

The same fault may fire a detection event repeatedly. Instead of creating one
incident per event (an incident storm), a fingerprint derived from
(source, type, scope, scope_id) maps all those detections to ONE incident
(spec sections 10, 11, 26).

Fingerprint != Incident ID:

    fingerprint:  POSITION_SERVICE|POSITION_INTEGRITY_FAILURE|STRATEGY_A
    incident id:  INC-00042
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional


class IncidentFingerprint:
    """A stable hash of the incident's deduplication components."""

    __slots__ = ("source", "incident_type", "scope", "scope_id", "value")

    def __init__(
        self,
        source: Any,
        incident_type: Any,
        scope: Any = None,
        scope_id: Optional[str] = None,
    ) -> None:
        from .incident_scope import IncidentScope
        from .incident_source import IncidentSource
        from .incident_type import IncidentType

        self.source = IncidentSource(source)
        self.incident_type = IncidentType(incident_type)
        self.scope = IncidentScope(scope) if scope is not None else None
        self.scope_id = scope_id
        self.value = self._compute()

    @property
    def components(self) -> List[str]:
        return [
            self.source.value,
            self.incident_type.value,
            self.scope.value if self.scope else "*",
            self.scope_id or "*",
        ]

    def _compute(self) -> str:
        canonical = "|".join(self.components)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def matches(self, other: "IncidentFingerprint") -> bool:
        """True if both fingerprints describe the same class of incident."""
        if not isinstance(other, IncidentFingerprint):
            raise TypeError(
                f"other must be IncidentFingerprint, got {type(other).__name__}"
            )
        return self.components == other.components

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint": self.value,
            "source": self.source.value,
            "incident_type": self.incident_type.value,
            "scope": self.scope.value if self.scope else None,
            "scope_id": self.scope_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentFingerprint":
        return cls(
            source=data["source"],
            incident_type=data["incident_type"],
            scope=data.get("scope"),
            scope_id=data.get("scope_id"),
        )

    # -- comparison -------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentFingerprint):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"IncidentFingerprint({self.value!r})"
