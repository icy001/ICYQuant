"""RecoveryRepository — persistence interface for recovery jobs.

In-memory implementation for testing; production would use SQL/event-store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecoveryRepository:
    """In-memory repository for RecoveryJob persistence.

    Supports:
        - Save / load by job_id
        - Query by recovery_key
        - Find active jobs for conflict detection
        - Job history retrieval
    """

    _store: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def save(self, job: Any) -> None:
        """Persist a recovery job (upsert)."""
        self._store[job.job_id] = job.to_dict()

    def get(self, job_id: str) -> Optional[Any]:
        """Retrieve a recovery job by ID."""
        data = self._store.get(job_id)
        if data is None:
            return None
        from services.recovery.domain.recovery_job import RecoveryJob
        return RecoveryJob.from_dict(data)

    def find_active(self) -> List[Any]:
        """Find all currently active (non-terminal) recovery jobs."""
        active = []
        for data in self._store.values():
            if data["status"] in ("CREATED", "PRECHECKING", "REPLAYING", "VERIFYING"):
                from services.recovery.domain.recovery_job import RecoveryJob
                active.append(RecoveryJob.from_dict(data))
        return active

    def find_by_key(self, recovery_key: str) -> List[Any]:
        """Find all jobs for a given recovery key."""
        results = []
        for data in self._store.values():
            scope = data.get("scope", {})
            key = _build_key(scope)
            if key == recovery_key:
                from services.recovery.domain.recovery_job import RecoveryJob
                results.append(RecoveryJob.from_dict(data))
        return results

    def find_active_by_key(self, recovery_key: str) -> Optional[Any]:
        """Find an active job for the given recovery key (conflict detection)."""
        for job in self.find_by_key(recovery_key):
            if job.is_active:
                return job
        return None

    def delete(self, job_id: str) -> None:
        """Remove a job from the repository."""
        self._store.pop(job_id, None)

    def count(self) -> int:
        return len(self._store)

    def count_by_status(self, status: str) -> int:
        return sum(1 for d in self._store.values() if d["status"] == status)

    def all_jobs(self) -> List[Any]:
        """Return all jobs."""
        from services.recovery.domain.recovery_job import RecoveryJob
        return [RecoveryJob.from_dict(d) for d in self._store.values()]


def _build_key(scope: Dict[str, Any]) -> str:
    parts = [scope["scope_type"]]
    for k in ("account_id", "instrument_id", "execution_id", "order_id"):
        if scope.get(k):
            parts.append(scope[k])
    return ":".join(parts)
