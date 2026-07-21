"""
Consensus monitor.
"""


class ConsensusMonitor:

    def metrics(
        self,
        records,
    ):

        return {
            "committed": len(records),
        }