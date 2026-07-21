"""
Scheduler monitor.
"""


class SchedulerMonitor:

    def metrics(
        self,
        queue,
    ):

        return {
            "pending_jobs": len(
                queue.jobs
            )
        }