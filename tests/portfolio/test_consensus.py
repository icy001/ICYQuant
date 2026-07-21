from services.portfolio import (
    LeaderCommit,
    LogReplication,
    PortfolioConsensusEngine,
    QuorumValidator,
)


def test_consensus():
    engine = PortfolioConsensusEngine(
        QuorumValidator(),
        LogReplication(),
        LeaderCommit(),
    )

    record = engine.execute(
        "CONSENSUS-001",
        "node-1",
        {"cash": 100},
        votes=2,
        nodes=[
            "node-1",
            "node-2",
            "node-3",
        ],
    )

    assert record.consensus_id == "CONSENSUS-001"