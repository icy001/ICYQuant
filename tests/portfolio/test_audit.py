from services.portfolio import (
    AuditRepository,
    AuditRecorder,
    PortfolioAuditEngine,
)


def test_audit_record():
    repository = AuditRepository()

    recorder = AuditRecorder()

    engine = PortfolioAuditEngine(
        recorder,
        repository,
    )

    engine.log(
        "AUDIT-001",
        "portfolio",
        "UPDATE",
        "admin",
        {},
    )

    assert len(
        repository.list_all()
    ) == 1