"""
Data drift detector.
"""


class DriftDetector:
    def compare(
        self,
        current,
        baseline,
    ):
        if current == baseline:
            return False
        return True