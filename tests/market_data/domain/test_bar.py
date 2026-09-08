"""Tests for Bar domain model."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import Exchange


class TestBarCreation:
    def test_basic_creation(self):
        bar = Bar(
            symbol="159852",
            exchange=Exchange.SZSE,
            timeframe="1m",
            timestamp=datetime.now(timezone.utc),
            open=Decimal("1.230"),
            high=Decimal("1.236"),
            low=Decimal("1.228"),
            close=Decimal("1.234"),
            volume=500000,
        )
        assert bar.symbol == "159852"
        assert bar.exchange == Exchange.SZSE
        assert bar.timeframe == "1m"
        assert bar.volume == 500000

    def test_defaults(self):
        bar = Bar(
            symbol="159852",
            exchange=Exchange.SZSE,
            timeframe="1m",
            timestamp=datetime.now(timezone.utc),
            open=Decimal("1.0"),
            high=Decimal("1.0"),
            low=Decimal("1.0"),
            close=Decimal("1.0"),
        )
        assert bar.volume == 0

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol must not be empty"):
            Bar(
                symbol="",
                exchange=Exchange.SZSE,
                timeframe="1m",
                timestamp=datetime.now(timezone.utc),
                open=Decimal("1.0"),
                high=Decimal("1.0"),
                low=Decimal("1.0"),
                close=Decimal("1.0"),
            )

    def test_empty_timeframe_raises(self):
        with pytest.raises(ValueError, match="timeframe must not be empty"):
            Bar(
                symbol="159852",
                exchange=Exchange.SZSE,
                timeframe="",
                timestamp=datetime.now(timezone.utc),
                open=Decimal("1.0"),
                high=Decimal("1.0"),
                low=Decimal("1.0"),
                close=Decimal("1.0"),
            )

    def test_naive_timestamp_raises(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            Bar(
                symbol="159852",
                exchange=Exchange.SZSE,
                timeframe="1m",
                timestamp=datetime.now(),
                open=Decimal("1.0"),
                high=Decimal("1.0"),
                low=Decimal("1.0"),
                close=Decimal("1.0"),
            )

    def test_as_dict(self):
        ts = datetime.now(timezone.utc)
        bar = Bar(
            symbol="513050",
            exchange=Exchange.SSE,
            timeframe="5m",
            timestamp=ts,
            open=Decimal("1.620"),
            high=Decimal("1.625"),
            low=Decimal("1.618"),
            close=Decimal("1.622"),
            volume=300000,
        )
        d = bar.as_dict()
        assert d["symbol"] == "513050"
        assert d["exchange"] == "SSE"
        assert d["timeframe"] == "5m"
        assert d["volume"] == 300000
        assert d["timestamp"] == ts.isoformat()
