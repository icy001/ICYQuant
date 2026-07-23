from services.platform.distributed import (
    ClusterManager,
    ClusterNode,
)


def test_cluster():

    cluster = ClusterManager()

    cluster.register(
        ClusterNode(
            "node-1",
            "localhost",
            0.2,
            0.3,
            "healthy",
        )
    )

    assert len(
        cluster.healthy_nodes()
    ) == 1