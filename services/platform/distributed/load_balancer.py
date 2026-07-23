"""
Agent load balancer.
"""


class LoadBalancer:

    def select(
        self,
        nodes,
    ):

        return min(
            nodes,
            key=lambda n: n.cpu_usage,
        )