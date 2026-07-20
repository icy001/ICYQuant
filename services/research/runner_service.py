"""
Runner service.
"""

from .controller import ExperimentController


class RunnerService:
    def __init__(
        self,
        controller: ExperimentController,
    ):
        self.controller = controller

    async def start(
        self,
        runner,
        experiment,
        context,
    ):
        return await self.controller.execute(
            runner,
            experiment,
            context,
        )