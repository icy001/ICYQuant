from services.data.catalog import (
    DatasetCatalog,
    DatasetEntry,
    Metadata,
    DataOwner,
    MetadataSearch,
    CatalogService,
)


def test_catalog_search():
    catalog = DatasetCatalog()

    catalog.register(
        DatasetEntry(
            name="NVDA_PRICE",
            description="price data",
            metadata=[Metadata("market", "US")],
        )
    )

    result = catalog.list_all()

    assert result[0].name == "NVDA_PRICE"


def test_metadata():
    metadata = Metadata(key="frequency", value="1min")

    assert metadata.key == "frequency"
    assert metadata.value == "1min"


def test_dataset_entry():
    entry = DatasetEntry(
        name="NASDAQ_TICK",
        description="US equity tick data",
        metadata=[Metadata("frequency", "tick")],
    )

    assert entry.name == "NASDAQ_TICK"
    assert entry.description == "US equity tick data"


def test_data_owner():
    owner = DataOwner(team="Quant Data Team", contact="data-team@icyquant.com")

    assert owner.team == "Quant Data Team"
    assert owner.contact == "data-team@icyquant.com"


def test_metadata_search():
    search = MetadataSearch()

    entries = [
        DatasetEntry(name="NVDA_PRICE", description="", metadata=[]),
        DatasetEntry(name="NVDA_OPTION_CHAIN", description="", metadata=[]),
        DatasetEntry(name="AAPL_PRICE", description="", metadata=[]),
    ]

    results = search.search(entries, "NVDA")

    assert len(results) == 2
    assert results[0].name == "NVDA_PRICE"
    assert results[1].name == "NVDA_OPTION_CHAIN"


def test_metadata_search_empty():
    search = MetadataSearch()

    entries = [DatasetEntry(name="AAPL_PRICE", description="", metadata=[])]

    results = search.search(entries, "NVDA")

    assert len(results) == 0


def test_catalog_service():
    catalog = DatasetCatalog()
    search = MetadataSearch()
    service = CatalogService(catalog, search)

    catalog.register(
        DatasetEntry(name="SP500_FEATURE", description="", metadata=[])
    )

    results = service.discover("SP500")

    assert len(results) == 1
    assert results[0].name == "SP500_FEATURE"