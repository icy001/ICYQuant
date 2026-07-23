"""
Circuit breaker foundation.
"""


class CircuitBreaker:

    def __init__(self):
        self.failures = 0
        self.open = False

    def record_failure(self):
        self.failures += 1

    def allow_request(self):
        return not self.open