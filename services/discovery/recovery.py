class RecoveryManager:
    def recover(self, instance):
        instance.healthy = True
        return instance
