"""
Task dispatcher.
"""


class TaskDispatcher:

    def dispatch(
        self,
        job,
        node,
    ):

        return {
            "job": job.job_id,
            "node": node.node_id,
        }