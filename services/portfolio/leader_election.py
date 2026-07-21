"""
Leader election.
"""


class LeaderElection:

    def elect(
        self,
        nodes,
    ):

        if not nodes:

            return None

        return sorted(
            nodes,
            key=lambda n: n.node_id,
        )[0]