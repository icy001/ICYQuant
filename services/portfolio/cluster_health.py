"""
Cluster health.
"""


class ClusterHealth:

    def summary(
        self,
        nodes,
    ):

        total = len(nodes)

        alive = sum(
            1 for n in nodes if n.alive
        )

        return {
            "total": total,
            "alive": alive,
        }