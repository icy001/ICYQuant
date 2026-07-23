from infrastructure.audit import (
    AuditRecord,
)


def test_audit_record():

    record = AuditRecord(

        "agent-001",

        "create-order",

        "2026-01-01",

        "SUCCESS"

    )


    assert record.result == "SUCCESS"