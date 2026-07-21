from services.portfolio import (
    VersionDiff,
    VersionRepository,
    PortfolioVersionEngine,
    PortfolioVersion,
    VersionQuery,
    VersionRollback,
    PortfolioVersionService,
    VersionSnapshot,
)


def test_version_diff():
    diff = VersionDiff()

    result = diff.compare(
        {"cash": 100},
        {"cash": 120},
    )

    assert "cash" in result


def test_version_record():
    from datetime import datetime

    version = PortfolioVersion(
        version_id="V001",
        portfolio_id="PF001",
        created_at=datetime.utcnow(),
        snapshot={"cash": 100},
    )

    assert version.version_id == "V001"
    assert version.portfolio_id == "PF001"
    assert version.snapshot == {"cash": 100}


def test_version_repository():
    repository = VersionRepository()

    from datetime import datetime

    version = PortfolioVersion(
        version_id="V001",
        portfolio_id="PF001",
        created_at=datetime.utcnow(),
        snapshot={"cash": 100},
    )

    repository.save(version)

    assert len(repository.list_all()) == 1


def test_version_engine():
    repository = VersionRepository()
    engine = PortfolioVersionEngine(repository)

    version = engine.create(
        version_id="V001",
        portfolio_id="PF001",
        snapshot={"cash": 100},
    )

    assert version.version_id == "V001"
    assert version.portfolio_id == "PF001"
    assert len(repository.list_all()) == 1


def test_version_query():
    repository = VersionRepository()
    query = VersionQuery(repository)

    from datetime import datetime

    version = PortfolioVersion(
        version_id="V001",
        portfolio_id="PF001",
        created_at=datetime.utcnow(),
        snapshot={"cash": 100},
    )

    repository.save(version)

    history = query.history()

    assert len(history) == 1


def test_version_rollback():
    from datetime import datetime

    version = PortfolioVersion(
        version_id="V001",
        portfolio_id="PF001",
        created_at=datetime.utcnow(),
        snapshot={"cash": 100},
    )

    rollback = VersionRollback()

    snapshot = rollback.rollback(version)

    assert snapshot == {"cash": 100}


def test_version_service():
    repository = VersionRepository()
    engine = PortfolioVersionEngine(repository)
    service = PortfolioVersionService(engine)

    version = service.create(
        version_id="V001",
        portfolio_id="PF001",
        snapshot={"cash": 100},
    )

    assert version.version_id == "V001"


def test_version_snapshot():
    snapshot = VersionSnapshot(
        latest_version="V001",
        total_versions=5,
    )

    assert snapshot.latest_version == "V001"
    assert snapshot.total_versions == 5


def test_version_diff_no_changes():
    diff = VersionDiff()

    result = diff.compare(
        {"cash": 100, "assets": {"AAPL": 50}},
        {"cash": 100, "assets": {"AAPL": 50}},
    )

    assert len(result) == 0


def test_version_diff_added_key():
    diff = VersionDiff()

    result = diff.compare(
        {"cash": 100},
        {"cash": 100, "assets": {"AAPL": 50}},
    )

    assert "assets" in result
    assert result["assets"]["before"] is None
    assert result["assets"]["after"] == {"AAPL": 50}