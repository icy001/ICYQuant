"""
Impact analysis.
"""


class ImpactAnalyzer:
    def __init__(
        self,
        lineage,
    ):
        self.lineage = lineage

    def analyze(
        self,
        node,
    ):
        return self.lineage.downstream(node)