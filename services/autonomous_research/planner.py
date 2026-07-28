from typing import List, Optional

from .goal import ResearchGoal
from .task import ResearchTask
from .workflow import ResearchWorkflow


class ResearchPlanner:
    """Converts research goals into executable task plans."""

    def __init__(self):
        self._task_counter = 0

    def plan(self, goal: ResearchGoal) -> ResearchWorkflow:
        """Generate a workflow from a research goal.

        Default planning decomposes the goal into a linear pipeline:
        feature -> model -> backtest
        """
        goal.mark_planned()

        workflow = ResearchWorkflow(
            workflow_id=f"WF_{goal.goal_id}",
            name=f"Workflow for: {goal.description}",
        )

        task_types = ["feature", "model", "backtest"]
        previous_id: Optional[str] = None

        for ttype in task_types:
            self._task_counter += 1
            task = ResearchTask(
                task_id=f"T{self._task_counter:03d}",
                task_type=ttype,
                goal_id=goal.goal_id,
                dependencies=[previous_id] if previous_id else [],
            )
            workflow.add_task(task)
            if previous_id:
                workflow.add_edge(previous_id, task.task_id)
            previous_id = task.task_id

        workflow.mark_started()
        return workflow

    def plan_custom(
        self, goal: ResearchGoal, task_types: List[str]
    ) -> ResearchWorkflow:
        """Generate a workflow with custom task types."""
        goal.mark_planned()

        workflow = ResearchWorkflow(
            workflow_id=f"WF_{goal.goal_id}",
            name=f"Workflow for: {goal.description}",
        )

        previous_id: Optional[str] = None

        for ttype in task_types:
            self._task_counter += 1
            task = ResearchTask(
                task_id=f"T{self._task_counter:03d}",
                task_type=ttype,
                goal_id=goal.goal_id,
                dependencies=[previous_id] if previous_id else [],
            )
            workflow.add_task(task)
            if previous_id:
                workflow.add_edge(previous_id, task.task_id)
            previous_id = task.task_id

        workflow.mark_started()
        return workflow
