from .status import LockStatus


class LockManager:
    def __init__(self, repository):
        self.repository = repository

    def acquire(self, request):
        current = self.repository.get(request.resource)

        if current and current.status == LockStatus.LOCKED:
            return False

        lock = {
            "resource": request.resource,
            "owner": request.owner,
            "status": LockStatus.LOCKED
        }

        self.repository.save(lock)
        return True

    def release(self, resource):
        lock = self.repository.get(resource)
        if lock:
            lock["status"] = LockStatus.AVAILABLE
        return True
