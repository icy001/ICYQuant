from services.data import (
    Dataset,
    DatasetRegistry,
)


def test_dataset_registry():

    registry = DatasetRegistry()

    dataset = Dataset(
        "DATASET001",
        "Daily Bars",
        "",
        {"close": "float"},
        "YAHOO",
    )

    registry.register(
        dataset,
    )

    assert registry.get(
        "DATASET001"
    ).name == "Daily Bars"