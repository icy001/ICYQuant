"""
Model artifact.
"""

from dataclasses import dataclass


@dataclass
class ModelArtifact:

    model_id: str

    name: str

    version: str

    path: str