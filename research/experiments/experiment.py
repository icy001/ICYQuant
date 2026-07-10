from dataclasses import dataclass
from typing import Dict, Optional

from .metadata import ExperimentMetadata


@dataclass
class Experiment:
    metadata: ExperimentMetadata
    result: Optional[Dict] = None

    def complete(self, result: Dict):
        self.result = result