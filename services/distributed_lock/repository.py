class LockRepository:
    def __init__(self):
        self.locks = {}

    def save(self, lock):
        key = lock["resource"] if isinstance(lock, dict) else lock.resource
        self.locks[key] = lock

    def get(self, resource):
        return self.locks.get(resource)
