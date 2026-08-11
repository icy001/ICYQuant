"""Execution Health — Health monitoring for execution subsystem."""
import time


class ExecutionHealth:
    def __init__(self):
        self._last_check = 0.0
        self._status = "HEALTHY"

    async def check(self) -> dict:
        self._last_check = time.time()
        return {"status": self._status, "timestamp": self._last_check}

    def set_status(self, status: str):
        self._status = status
