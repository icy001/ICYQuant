from enum import Enum


class FundStatus(Enum):
    CREATED = "created"
    ACTIVE = "active"
    CLOSED = "closed"


class FundLifecycleManager:
    def create(self, name):
        return {"fund": name, "status": FundStatus.CREATED.value}
