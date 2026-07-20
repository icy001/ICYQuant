"""
Walk-forward executor.
"""


class WalkForwardExecutor:
    async def execute(
        self,
        windows,
        runner,
    ):
        results = []
        for window in windows:
            results.append(await runner.run(window))
        return results