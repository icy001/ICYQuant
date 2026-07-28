from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ResearchGoal:
    """Represents a research goal to be autonomously planned and executed."""

    goal_id: str
    description: str
    priority: int = 1
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def mark_planned(self) -> None:
        self.status = "PLANNED"

    def mark_completed(self) -> None:
        self.status = "COMPLETED"
        self.completed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        self.status = "FAILED"
