from typing import Any, Dict, List, Optional

from .evaluator import ResearchEvaluator
from .experiment import ExperimentLoop
from .goal import ResearchGoal
from .planner import ResearchPlanner
from .scheduler import TaskScheduler


class AutonomousResearchService:
    """Orchestrates the full autonomous research lifecycle.

    Pipeline: Goal -> Plan -> Execute -> Experiment -> Evaluate
    """

    def __init__(
        self,
        planner: ResearchPlanner,
        scheduler: Optional[TaskScheduler] = None,
        experiment_loop: Optional[ExperimentLoop] = None,
        evaluator: Optional[ResearchEvaluator] = None,
    ):
        self.planner = planner
        self.scheduler = scheduler or TaskScheduler()
        self.experiment_loop = experiment_loop or ExperimentLoop()
        self.evaluator = evaluator or ResearchEvaluator()

    def run(self, goal: ResearchGoal) -> List[str]:
        """Execute the full pipeline for a research goal.

        Returns the list of task types from planning.
        """
        workflow = self.planner.plan(goal)
        return [t.task_type for t in workflow.tasks]

    def run_full(
        self, goal: ResearchGoal
    ) -> Dict[str, Any]:
        """Execute the full pipeline including experiment and evaluation."""
        # Step 1: Plan
        workflow = self.planner.plan(goal)

        # Step 2: Execute tasks
        task_results = self.scheduler.execute(workflow)

        # Step 3: Run experiment
        experiment_result = self.experiment_loop.run(goal.description)

        # Step 4: Evaluate
        evaluation = self.evaluator.evaluate(experiment_result)

        goal.mark_completed()

        return {
            "goal_id": goal.goal_id,
            "description": goal.description,
            "status": goal.status,
            "task_count": len(workflow.tasks),
            "task_results": task_results,
            "experiment": {
                "iteration": experiment_result.iteration,
                "metrics": experiment_result.metrics,
            },
            "evaluation": {
                "score": evaluation.score,
                "decision": evaluation.decision,
                "reason": evaluation.reason,
            },
        }

    def run_with_custom_tasks(
        self, goal: ResearchGoal, task_types: List[str]
    ) -> Dict[str, Any]:
        """Run research with custom task types."""
        workflow = self.planner.plan_custom(goal, task_types)
        task_results = self.scheduler.execute(workflow)
        experiment_result = self.experiment_loop.run(goal.description)
        evaluation = self.evaluator.evaluate(experiment_result)
        goal.mark_completed()

        return {
            "goal_id": goal.goal_id,
            "task_types": task_types,
            "task_results": task_results,
            "evaluation_decision": evaluation.decision,
            "evaluation_score": evaluation.score,
        }
