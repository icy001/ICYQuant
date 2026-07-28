class ExpirationManager:
    def expire(self, lock):
        lock.status = "EXPIRED"
        return lock
