"""
Node load balancer.
"""


class LoadBalancer:

    def select_node(
        self,
        nodes,
    ):

        if not nodes:

            return None

        return min(
            nodes,
            key=lambda n: n.node_id,
        )