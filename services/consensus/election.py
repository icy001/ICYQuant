from .state import NodeState


class LeaderElection:
    def elect(self, node):
        node.state = NodeState.LEADER
        return node
