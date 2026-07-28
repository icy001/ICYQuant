from .status import ServiceStatus


class HealthMonitor:
    def check(self, instance):
        return ServiceStatus.UP if instance.status == ServiceStatus.UP else ServiceStatus.DOWN
