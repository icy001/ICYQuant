"""
Anomaly detector.
"""


class AnomalyDetector:
    def detect(
        self,
        value,
        threshold,
    ):
        return abs(value) > threshold