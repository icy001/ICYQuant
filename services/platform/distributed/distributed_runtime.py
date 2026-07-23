"""
Distributed runtime.
"""


class DistributedRuntime:

    def __init__(
        self,
        cluster_manager,
    ):

        self.cluster = cluster_manager

    def execute(
        self,
        task,
    ):

        nodes = self.cluster.healthy_nodes()

        if not nodes:

            raise RuntimeError(
                "No healthy node."
            )

        return nodes[0].node_id