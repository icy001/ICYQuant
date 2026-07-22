"""
Research artifact model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ResearchArtifact:

    artifact_id: str

    project_id: str = ""

    artifact_type: str = ""

    name: str = ""

    version: str = ""

    created_at: datetime = None

    uri: str = ""

    experiment_id: str = ""

    location: str = ""

    def __post_init__(self):
        if self.created_at is None:
            import datetime
            self.created_at = datetime.datetime.utcnow()