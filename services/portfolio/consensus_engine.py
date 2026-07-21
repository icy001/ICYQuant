"""
Portfolio distributed consensus engine.
"""

from datetime import datetime

from .consensus_record import ConsensusRecord


class PortfolioConsensusEngine:

    def __init__(
        self,
        quorum,
        replication,
        commit,
    ):

        self.quorum = quorum

        self.replication = replication

        self.commit = commit

    def execute(
        self,
        consensus_id,
        leader,
        payload,
        votes,
        nodes,
    ):

        if not self.quorum.validate(
            votes,
            len(nodes),
        ):

            raise ValueError(
                "Quorum not reached"
            )

        record = ConsensusRecord(
            consensus_id=consensus_id,
            term=1,
            leader_id=leader,
            committed_at=datetime.utcnow(),
            payload=payload,
        )

        self.replication.replicate(
            record,
            nodes,
        )

        return self.commit.commit(
            record,
        )