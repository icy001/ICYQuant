from typing import Dict, List


class ReconciliationRepository:
    def __init__(self) -> None:
        self._records = []

    def save(self, record: Dict) -> None:
        self._records.append(record)

    def get_by_run_id(self, run_id: str):
        for record in self._records:
            if record.get("run_id") == run_id:
                return record
        return None

    def get_all(self) -> List[Dict]:
        return self._records
