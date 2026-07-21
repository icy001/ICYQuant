"""
Replication health checker.
"""


class ReplicationHealthChecker:
    def check(
        self,
        result,
    ):
        return result.get("replicated", False)