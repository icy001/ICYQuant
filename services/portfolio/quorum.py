"""
Quorum validator.
"""


class QuorumValidator:

    def validate(
        self,
        votes,
        total_nodes,
    ):

        return votes > total_nodes // 2