"""
Research artifact model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    experiment_id: str
    artifact_type: str
    location: str