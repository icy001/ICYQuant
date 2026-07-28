from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ResearchTask:
    """Represents a single research task within a workflow."""

    task_id: str
    task_type: str
    status: str = "PENDING"
    goal_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def mark_running(self) -> None:
        self.status = "RUNNING"
        self.started_at = datetime.utcnow()

    def mark_completed(self, result: Dict[str, Any] = None) -> None:
        self.status = "COMPLETED"
        self.completed_at = datetime.utcnow()
        if result is not None:
            self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = "FAILED"
        self.result = {"error": error}
