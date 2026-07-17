"""
Factor turnover analyzer.
"""


class TurnoverAnalyzer:
    def calculate(
        self,
        previous,
        current,
    ):
        if not previous:
            return 0

        changes = sum(
            1 for a, b in zip(previous, current) if a != b
        )

        return changes / len(previous)