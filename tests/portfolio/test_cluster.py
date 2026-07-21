from services.portfolio import (
    ClusterNode,
    ClusterRepository,
    LeaderElection,
    PortfolioClusterCoordinator,
)


def test_leader_election():
    repository = ClusterRepository()

    repository.register(
        ClusterNode(
            "node-2",
            "10.0.0.2",
            "FOLLOWER",
        )
    )

    repository.register(
        ClusterNode(
            "node-1",
            "10.0.0.1",
            "LEADER",
        )
    )

    coordinator = PortfolioClusterCoordinator(
        repository,
        LeaderElection(),
    )

    leader = coordinator.leader()

    assert leader.node_id == "node-1"