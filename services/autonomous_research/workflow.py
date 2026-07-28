from typing import Dict, List, Optional

from .task import ResearchTask


class ResearchWorkflow:
    """Represents a directed acyclic graph of research tasks."""

    def __init__(self, workflow_id: str = "", name: str = ""):
        self.workflow_id = workflow_id
        self.name = name
        self.tasks: List[ResearchTask] = []
        self.edges: Dict[str, List[str]] = {}  # task_id -> [next_task_ids]
        self.status: str = "CREATED"

    def add_task(self, task: ResearchTask) -> None:
        self.tasks.append(task)
        if task.task_id not in self.edges:
            self.edges[task.task_id] = []

    def add_edge(self, from_task_id: str, to_task_id: str) -> None:
        if from_task_id not in self.edges:
            self.edges[from_task_id] = []
        self.edges[from_task_id].append(to_task_id)

    def get_next_tasks(self, task_id: str) -> List[str]:
        return self.edges.get(task_id, [])

    def get_ready_tasks(self) -> List[ResearchTask]:
        """Returns tasks whose dependencies are all completed."""
        completed_ids = {
            t.task_id for t in self.tasks if t.status == "COMPLETED"
        }
        ready = []
        for task in self.tasks:
            if task.status == "PENDING":
                deps_met = all(
                    dep in completed_ids for dep in task.dependencies
                )
                if deps_met:
                    ready.append(task)
        return ready

    def mark_started(self) -> None:
        self.status = "RUNNING"

    def mark_completed(self) -> None:
        self.status = "COMPLETED"

    def mark_failed(self) -> None:
        self.status = "FAILED"

    def is_complete(self) -> bool:
        return all(t.status in ("COMPLETED", "FAILED") for t in self.tasks)

    def summary(self) -> dict:
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == "COMPLETED")
        failed = sum(1 for t in self.tasks if t.status == "FAILED")
        running = sum(1 for t in self.tasks if t.status == "RUNNING")
        pending = sum(1 for t in self.tasks if t.status == "PENDING")
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
        }
