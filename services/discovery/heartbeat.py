class HeartbeatManager:
    def heartbeat(self, instance):
        instance.healthy = True
        return instance
