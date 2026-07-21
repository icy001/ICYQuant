"""
Task failover.
"""


class TaskFailover:

    def migrate(
        self,
        job,
        target_node,
    ):

        return {
            "job": job.job_id,
            "target": target_node.node_id,
        }