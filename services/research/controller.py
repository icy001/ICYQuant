"""
Experiment execution controller.
"""


class ExperimentController:
    async def execute(
        self,
        runner,
        experiment,
        context,
    ):
        return await runner.run(experiment, context)