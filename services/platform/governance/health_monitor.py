"""
Agent health monitor.
"""

import time


class HealthMonitor:

    def heartbeat(self, agent):

        return {
            "agent": agent,
            "timestamp": time.time(),
            "healthy": True,
        }