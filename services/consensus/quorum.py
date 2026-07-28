class QuorumManager:
    def quorum(self, nodes):
        return len(nodes) // 2 + 1
