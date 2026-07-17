"""
Pipeline scheduler.
"""


class PipelineScheduler:
    def schedule(
        self,
        dag,
    ):
        return list(dag.tasks.values())