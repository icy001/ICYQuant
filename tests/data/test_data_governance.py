from services.data import (
    MetadataCatalog,
    SchemaRegistry,
    DataGovernanceService,
    DataLineage,
)


def test_metadata_catalog():

    catalog = MetadataCatalog()

    catalog.register(
        "bars",
        {"owner": "research"},
    )

    assert catalog.get(
        "bars"
    )["owner"] == "research"


def test_schema_registry():

    registry = SchemaRegistry()

    registry.register(
        "bars",
        {"close": "float"},
    )

    assert registry.get(
        "bars"
    )["close"] == "float"