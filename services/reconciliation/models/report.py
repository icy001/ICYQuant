from dataclasses import dataclass, field
from datetime import datetime

from .difference import Difference


@dataclass
class ReconciliationReport:
    differences: list[Difference] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def healthy(self) -> bool:
        return len(self.differences) == 0
