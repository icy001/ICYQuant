"""Incident Memory — Records incident patterns for prevention."""
import time


class IncidentMemory:
    def __init__(self):
        self._records: list[dict] = []

    def record(self, incident_type: str, outcome: str, learnings: str):
        self._records.append({
            "incident_type": incident_type,
            "outcome": outcome,
            "learnings": learnings,
            "timestamp": time.time(),
        })

    def stats(self) -> dict:
        return {"records": len(self._records)}
