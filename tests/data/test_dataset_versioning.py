from datetime import datetime

from services.data.dataset import (
    Dataset,
    DatasetRegistry,
    DatasetVersion,
    DatasetSnapshot,
    DataLineage,
    DatasetService,
)


def test_dataset_registry():
    registry = DatasetRegistry()

    dataset = Dataset(
        name="NASDAQ",
        description="equity data",
    )

    registry.register(dataset)

    assert registry.get("NASDAQ") == dataset


def test_dataset_version():
    version = DatasetVersion(
        dataset_name="NASDAQ_US_EQUITY",
        version="2026.07.17",
    )

    assert version.dataset_name == "NASDAQ_US_EQUITY"
    assert version.version == "2026.07.17"


def test_dataset_snapshot():
    snapshot = DatasetSnapshot(
        dataset="NASDAQ",
        version="2026.07.17",
        created_at=datetime(2026, 7, 17, 9, 30, 0),
    )

    assert snapshot.dataset == "NASDAQ"
    assert snapshot.created_at.hour == 9


def test_data_lineage():
    lineage = DataLineage()

    lineage.add_relation("Market Data", "Feature")
    lineage.add_relation("Feature", "Factor")
    lineage.add_relation("Factor", "Strategy")

    downstream = lineage.downstream("Market Data")

    assert "Feature" in downstream


def test_data_lineage_multi():
    lineage = DataLineage()

    lineage.add_relation("Market Data", "Feature A")
    lineage.add_relation("Market Data", "Feature B")

    downstream = lineage.downstream("Market Data")

    assert "Feature A" in downstream
    assert "Feature B" in downstream


def test_dataset_service():
    registry = DatasetRegistry()
    service = DatasetService(registry)

    dataset = Dataset(name="NYSE", description="US stocks")
    registry.register(dataset)

    result = service.resolve("NYSE")

    assert result == dataset