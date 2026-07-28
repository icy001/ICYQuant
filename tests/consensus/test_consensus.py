from services.consensus import *


def test_leader_election():
    node = Node(
        "NODE001",
        NodeState.FOLLOWER,
        1
    )

    service = ConsensusService()
    leader = service.elect_leader(node)

    assert leader.state == NodeState.LEADER
