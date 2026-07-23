"""
Failure detection engine.
"""


class FailureDetector:

    def detect(
        self,
        health,
    ):
        return health.get(
            "status"
        ) != "healthy"