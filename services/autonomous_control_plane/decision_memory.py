"""Decision Memory — Records decision outcomes for learning."""
import time


class DecisionMemory:
    def __init__(self):
        self._records: list[dict] = []

    def record(self, decision_id: str, outcome: str, quality: float):
        self._records.append({
            "decision_id": decision_id,
            "outcome": outcome,
            "quality": quality,
            "timestamp": time.time(),
        })

    def stats(self) -> dict:
        return {"records": len(self._records)}
