"""
Replication executor.
"""


class ReplicationExecutor:
    def replicate(
        self,
        source,
        target,
    ):
        return {
            "source": source,
            "target": target,
            "replicated": True,
        }