"""
Experiment runner.
"""

from .result import ExperimentResult


class ExperimentRunner:
    async def run(
        self,
        experiment,
        context,
    ) -> ExperimentResult:
        return ExperimentResult(
            experiment_id=experiment.experiment_id,
            status="COMPLETED",
        )