"""
Execution monitor.
"""


class ExecutionMonitor:

    def metrics(
        self,
        results,
    ):

        return {
            "completed": len(
                results
            )
        }