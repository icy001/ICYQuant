"""
Service heartbeat manager.
"""

import time


class Heartbeat:

    def __init__(self):
        self.timestamps = {}

    def beat(
        self,
        service,
    ):
        self.timestamps[service] = time.time()

    def last_seen(
        self,
        service,
    ):
        return self.timestamps.get(service)