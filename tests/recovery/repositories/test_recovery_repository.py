"""Tests for RecoveryRepository — in-memory persistence."""

from __future__ import annotations

from services.recovery.domain.recovery_job import RecoveryJob, RecoveryPlan
from services.recovery.domain.recovery_scope import RecoveryScope
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType
from services.recovery.repositories.recovery_repository import RecoveryRepository


def _job(job_id="REC-001", status=RecoveryStatus.CREATED):
    job = RecoveryJob(
        job_id=job_id,
        recovery_type=RecoveryType.POSITION_REPLAY,
        scope=RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA"),
        source_check_id="CHECK-001",
    )
    job.status = status
    return job


class TestRecoveryRepository:
    """Tests for RecoveryRepository."""

    def test_save_and_get(self) -> None:
        repo = RecoveryRepository()
        job = _job()
        repo.save(job)
        retrieved = repo.get("REC-001")
        assert retrieved is not None
        assert retrieved.job_id == "REC-001"
        assert retrieved.recovery_key == "EXECUTION:ACC-001:NVDA:EXEC-001"

    def test_get_nonexistent(self) -> None:
        repo = RecoveryRepository()
        assert repo.get("NONEXISTENT") is None

    def test_count(self) -> None:
        repo = RecoveryRepository()
        assert repo.count() == 0
        repo.save(_job("REC-001"))
        repo.save(_job("REC-002"))
        assert repo.count() == 2

    def test_save_is_upsert(self) -> None:
        repo = RecoveryRepository()
        job = _job()
        repo.save(job)

        job.mark_prechecking()
        repo.save(job)
        retrieved = repo.get("REC-001")
        assert retrieved.status == RecoveryStatus.PRECHECKING

    def test_find_active(self) -> None:
        repo = RecoveryRepository()
        j1 = _job("REC-001", RecoveryStatus.CREATED)
        j2 = _job("REC-002", RecoveryStatus.REPLAYING)
        j3 = _job("REC-003", RecoveryStatus.COMPLETED)
        repo.save(j1)
        repo.save(j2)
        repo.save(j3)

        active = repo.find_active()
        assert len(active) == 2
        ids = {j.job_id for j in active}
        assert ids == {"REC-001", "REC-002"}

    def test_find_by_key(self) -> None:
        repo = RecoveryRepository()
        repo.save(_job("REC-001"))
        repo.save(_job("REC-002"))
        results = repo.find_by_key("EXECUTION:ACC-001:NVDA:EXEC-001")
        assert len(results) == 2

    def test_find_by_key_none(self) -> None:
        repo = RecoveryRepository()
        results = repo.find_by_key("NONEXISTENT")
        assert len(results) == 0

    def test_find_active_by_key(self) -> None:
        repo = RecoveryRepository()
        active_job = _job("REC-001", RecoveryStatus.CREATED)
        done_job = _job("REC-002", RecoveryStatus.COMPLETED)
        repo.save(active_job)
        repo.save(done_job)

        found = repo.find_active_by_key("EXECUTION:ACC-001:NVDA:EXEC-001")
        assert found is not None
        assert found.job_id == "REC-001"

    def test_delete(self) -> None:
        repo = RecoveryRepository()
        repo.save(_job("REC-001"))
        assert repo.count() == 1
        repo.delete("REC-001")
        assert repo.count() == 0
        assert repo.get("REC-001") is None

    def test_count_by_status(self) -> None:
        repo = RecoveryRepository()
        repo.save(_job("REC-001", RecoveryStatus.CREATED))
        repo.save(_job("REC-002", RecoveryStatus.CREATED))
        repo.save(_job("REC-003", RecoveryStatus.COMPLETED))
        assert repo.count_by_status("CREATED") == 2
        assert repo.count_by_status("COMPLETED") == 1

    def test_all_jobs(self) -> None:
        repo = RecoveryRepository()
        repo.save(_job("REC-001"))
        repo.save(_job("REC-002"))
        all_jobs = repo.all_jobs()
        assert len(all_jobs) == 2
