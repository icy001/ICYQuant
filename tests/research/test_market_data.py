import pytest
from datetime import datetime

from research.data.bar import Bar
from research.data.types import TimeFrame
from research.data.exceptions import MarketDataError, SymbolNotFoundError, InvalidTimeframeError


class TestBar:
    def test_bar_creation(self):
        bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15, 10, 30),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )

        assert bar.symbol == "NVDA"
        assert bar.timestamp == datetime(2024, 1, 15, 10, 30)
        assert bar.open == 480.0
        assert bar.high == 490.0
        assert bar.low == 475.0
        assert bar.close == 485.0
        assert bar.volume == 1000000

    def test_bar_typical_price(self):
        bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )

        assert bar.typical_price() == (490.0 + 475.0 + 485.0) / 3

    def test_bar_is_bullish(self):
        bullish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )
        assert bullish_bar.is_bullish() is True
        assert bullish_bar.is_bearish() is False

    def test_bar_is_bearish(self):
        bearish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=485.0,
            high=490.0,
            low=475.0,
            close=480.0,
            volume=1000000,
        )
        assert bearish_bar.is_bearish() is True
        assert bearish_bar.is_bullish() is False

    def test_bar_range(self):
        bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )
        assert bar.range() == 15.0

    def test_bar_body_range(self):
        bullish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )
        assert bullish_bar.body_range() == 5.0

        bearish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=485.0,
            high=490.0,
            low=475.0,
            close=480.0,
            volume=1000000,
        )
        assert bearish_bar.body_range() == 5.0

    def test_bar_wicks(self):
        bullish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=480.0,
            high=490.0,
            low=475.0,
            close=485.0,
            volume=1000000,
        )
        assert bullish_bar.upper_wick() == 5.0
        assert bullish_bar.lower_wick() == 5.0

        bearish_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 15),
            open=485.0,
            high=490.0,
            low=475.0,
            close=480.0,
            volume=1000000,
        )
        assert bearish_bar.upper_wick() == 5.0
        assert bearish_bar.lower_wick() == 5.0


class TestTimeFrame:
    def test_timeframe_values(self):
        assert TimeFrame.M1.value == "1m"
        assert TimeFrame.M5.value == "5m"
        assert TimeFrame.M15.value == "15m"
        assert TimeFrame.H1.value == "1h"
        assert TimeFrame.D1.value == "1d"

    def test_timeframe_enum_members(self):
        members = list(TimeFrame)
        assert len(members) == 9


class TestMarketDataExceptions:
    def test_market_data_error(self):
        with pytest.raises(MarketDataError):
            raise MarketDataError("Test error")

    def test_symbol_not_found_error(self):
        with pytest.raises(SymbolNotFoundError):
            raise SymbolNotFoundError("Symbol not found")

    def test_invalid_timeframe_error(self):
        with pytest.raises(InvalidTimeframeError):
            raise InvalidTimeframeError("Invalid timeframe")