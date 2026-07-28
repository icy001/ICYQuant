from .health import HealthStatus


class HealthChecker:
    def check(self, latency):
        if latency < 100:
            return HealthStatus.UP

        if latency < 1000:
            return HealthStatus.DEGRADED

        return HealthStatus.DOWN