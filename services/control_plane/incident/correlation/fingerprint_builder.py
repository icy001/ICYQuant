"""
FingerprintBuilder — stable deduplication key from detection components.

The fingerprint is the contract between Detection and Incident creation:
same source + incident type + scope + scope_id  =>  same incident.

    sha256(source | type | scope | scope_id)

The event_type is deliberately excluded: the same incident can surface through
different event types (down -> degraded -> flapping) and must still collapse
into ONE incident (spec section 43: incident-storm shield).
"""

from __future__ import annotations

from typing import Optional

from ..incident_fingerprint import IncidentFingerprint
from ..incident_scope import IncidentScope
from ..incident_source import IncidentSource
from ..incident_type import IncidentType


class FingerprintBuilder:
    """Build stable incident fingerprints from detection components."""

    def build(
        self,
        *,
        event_type: str = "",
        incident_type: Optional[IncidentType] = None,
        source: Optional[IncidentSource] = None,
        scope: Optional[IncidentScope] = None,
        service: str = "",
        account: str = "",
        strategy: str = "",
        instrument: str = "",
        venue: str = "",
    ) -> IncidentFingerprint:
        """Return the IncidentFingerprint for a detection.

        ``event_type`` is accepted for API symmetry but is intentionally not
        part of the fingerprint — see the module docstring. The scope_id is
        derived from the most specific available component.
        """
        scope_id = service or account or strategy or instrument or venue
        return IncidentFingerprint(
            source=IncidentSource(source) if source else IncidentSource.MANUAL,
            incident_type=(
                IncidentType(incident_type)
                if incident_type
                else IncidentType.SYSTEM_FAILURE
            ),
            scope=IncidentScope(scope) if scope else IncidentScope.GLOBAL,
            scope_id=scope_id,
        )
