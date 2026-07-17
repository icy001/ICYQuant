from decimal import Decimal
from datetime import datetime

import pytest

from services.data.market import (
    Tick,
    Bar,
    Dataset,
    DataType,
    MarketDataRepository,
    MarketDataIngestion,
)


def test_tick_creation():
    tick = Tick(
        symbol="NVDA",
        price=Decimal("180"),
        volume=Decimal("100"),
        timestamp=datetime.now(),
    )

    assert tick.symbol == "NVDA"
    assert tick.price == Decimal("180")


def test_bar_creation():
    bar = Bar(
        symbol="AAPL",
        open=Decimal("150"),
        high=Decimal("155"),
        low=Decimal("148"),
        close=Decimal("152"),
        volume=Decimal("1000"),
        timestamp=datetime.now(),
    )

    assert bar.symbol == "AAPL"
    assert bar.high >= bar.low
    assert bar.volume > Decimal("0")


def test_dataset_creation():
    dataset = Dataset(
        name="NASDAQ_US_EQUITY",
        version="2026.07.17",
        description="NASDAQ US Equity Daily Bars",
    )

    assert dataset.name == "NASDAQ_US_EQUITY"
    assert dataset.version == "2026.07.17"


def test_data_type_enum():
    assert DataType.TICK.value == "TICK"
    assert DataType.BAR.value == "BAR"


@pytest.mark.asyncio
async def test_repository_save():
    repo = MarketDataRepository()
    tick = Tick("NVDA", Decimal("180"), Decimal("100"), datetime.now())

    await repo.save(tick)

    assert len(repo.storage) == 1


@pytest.mark.asyncio
async def test_ingestion_pipeline():
    repo = MarketDataRepository()
    ingestion = MarketDataIngestion(repo)
    tick = Tick("NVDA", Decimal("180"), Decimal("100"), datetime.now())

    await ingestion.ingest(tick)

    assert len(repo.storage) == 1