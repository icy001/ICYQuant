"""
Artifact metadata.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactMetadata:
    version: str
    created_by: str
    tags: list[str]