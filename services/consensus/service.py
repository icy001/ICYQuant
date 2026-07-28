from .election import LeaderElection


class ConsensusService:
    def __init__(self):
        self.election = LeaderElection()

    def elect_leader(self, node):
        return self.election.elect(node)
