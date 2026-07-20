"""
Strategy execution simulator.
"""


class ExecutionSimulator:
    async def execute(
        self,
        signal,
        oms,
    ):
        order = oms.create_order(signal)
        return await oms.submit(order)