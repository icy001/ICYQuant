from services.portfolio import (
    ReplicationExecutor,
    ReplicationRepository,
    PortfolioReplicationEngine,
    ReplicationRecord,
    ReplicationStatus,
    ReplicationHealthChecker,
    PortfolioReplicationService,
    FailoverManager,
)


def test_replication():
    repository = ReplicationRepository()
    engine = PortfolioReplicationEngine(
        ReplicationExecutor(),
        repository,
    )

    result = engine.replicate(
        "REPL-001",
        "primary",
        "standby",
    )

    assert result.status == "SUCCESS"


def test_replication_record():
    from datetime import datetime

    record = ReplicationRecord(
        replication_id="REPL-001",
        source_node="primary",
        target_node="standby",
        created_at=datetime.utcnow(),
        status="SUCCESS",
    )

    assert record.replication_id == "REPL-001"
    assert record.source_node == "primary"
    assert record.target_node == "standby"
    assert record.status == "SUCCESS"


def test_replication_status():
    assert ReplicationStatus.PENDING.value == "PENDING"
    assert ReplicationStatus.RUNNING.value == "RUNNING"
    assert ReplicationStatus.SUCCESS.value == "SUCCESS"
    assert ReplicationStatus.FAILED.value == "FAILED"


def test_replication_repository():
    repository = ReplicationRepository()

    from datetime import datetime

    record = ReplicationRecord(
        replication_id="REPL-001",
        source_node="primary",
        target_node="standby",
        created_at=datetime.utcnow(),
        status="SUCCESS",
    )

    repository.save(record)

    assert len(repository.list_all()) == 1


def test_replication_executor():
    executor = ReplicationExecutor()

    result = executor.replicate("primary", "standby")

    assert result["source"] == "primary"
    assert result["target"] == "standby"
    assert result["replicated"] is True


def test_replication_health_checker():
    checker = ReplicationHealthChecker()

    result = {"replicated": True}

    assert checker.check(result) is True

    result_failed = {"replicated": False}

    assert checker.check(result_failed) is False


def test_replication_service():
    repository = ReplicationRepository()
    engine = PortfolioReplicationEngine(
        ReplicationExecutor(),
        repository,
    )
    service = PortfolioReplicationService(engine)

    result = service.replicate(
        "REPL-001",
        "primary",
        "standby",
    )

    assert result.status == "SUCCESS"


def test_failover_manager():
    manager = FailoverManager()

    result = manager.activate("standby-node-01")

    assert result["active_node"] == "standby-node-01"