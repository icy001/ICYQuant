"""
Execution simulation service.
"""


class ExecutionService:
    def __init__(
        self,
        simulator,
    ):
        self.simulator = simulator

    async def execute(
        self,
        signal,
        oms,
    ):
        return await self.simulator.execute(signal, oms)