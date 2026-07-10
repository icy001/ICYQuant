import pytest
from pathlib import Path
from datetime import datetime

from research.data.csv_provider import CsvMarketDataProvider
from research.data.types import TimeFrame
from research.data.exceptions import SymbolNotFoundError, DataFormatError
from research.data.validators import validate_bar_data, validate_ohlc_consistency

DATA_DIR = Path(__file__).parent / "sample"


class TestCsvMarketDataProvider:
    def test_load_csv_basic(self):
        provider = CsvMarketDataProvider(DATA_DIR)

        bars = provider.load_bars(
            "NVDA",
            TimeFrame.D1,
        )

        assert len(bars) == 10
        assert bars[0].symbol == "NVDA"
        assert bars[0].timestamp == datetime(2025, 1, 2)
        assert bars[0].open == 134.22
        assert bars[0].high == 136.50
        assert bars[0].low == 133.80
        assert bars[0].close == 136.01
        assert bars[0].volume == 50234567.0

    def test_load_csv_with_date_filter(self):
        provider = CsvMarketDataProvider(DATA_DIR)

        bars = provider.load_bars(
            "NVDA",
            TimeFrame.D1,
            start=datetime(2025, 1, 6),
            end=datetime(2025, 1, 10),
        )

        assert len(bars) == 5
        assert bars[0].timestamp == datetime(2025, 1, 6)
        assert bars[-1].timestamp == datetime(2025, 1, 10)

    def test_symbol_not_found(self):
        provider = CsvMarketDataProvider(DATA_DIR)

        with pytest.raises(SymbolNotFoundError):
            provider.load_bars("AAPL", TimeFrame.D1)

    def test_invalid_timeframe(self):
        provider = CsvMarketDataProvider(DATA_DIR)

        with pytest.raises(SymbolNotFoundError):
            provider.load_bars("NVDA", TimeFrame.H1)

    def test_bars_are_sorted_by_timestamp(self):
        provider = CsvMarketDataProvider(DATA_DIR)

        bars = provider.load_bars("NVDA", TimeFrame.D1)

        for i in range(1, len(bars)):
            assert bars[i].timestamp > bars[i - 1].timestamp


class TestValidators:
    def test_validate_bar_data_valid(self):
        row = {
            "timestamp": "2025-01-02",
            "open": "134.22",
            "high": "136.50",
            "low": "133.80",
            "close": "136.01",
            "volume": "50234567",
        }
        validate_bar_data(row)

    def test_validate_bar_data_missing_column(self):
        row = {
            "timestamp": "2025-01-02",
            "open": "134.22",
            "high": "136.50",
            "low": "133.80",
            "close": "136.01",
        }
        with pytest.raises(DataFormatError):
            validate_bar_data(row)

    def test_validate_bar_data_invalid_numeric(self):
        row = {
            "timestamp": "2025-01-02",
            "open": "invalid",
            "high": "136.50",
            "low": "133.80",
            "close": "136.01",
            "volume": "50234567",
        }
        with pytest.raises(DataFormatError):
            validate_bar_data(row)

    def test_validate_bar_data_invalid_timestamp(self):
        row = {
            "timestamp": "invalid-date",
            "open": "134.22",
            "high": "136.50",
            "low": "133.80",
            "close": "136.01",
            "volume": "50234567",
        }
        with pytest.raises(DataFormatError):
            validate_bar_data(row)

    def test_validate_ohlc_consistency_valid(self):
        validate_ohlc_consistency(134.22, 136.50, 133.80, 136.01)

    def test_validate_ohlc_consistency_high_less_than_low(self):
        with pytest.raises(DataFormatError):
            validate_ohlc_consistency(134.22, 133.00, 135.00, 136.01)

    def test_validate_ohlc_consistency_open_outside_range(self):
        with pytest.raises(DataFormatError):
            validate_ohlc_consistency(132.00, 136.50, 133.80, 136.01)

    def test_validate_ohlc_consistency_close_outside_range(self):
        with pytest.raises(DataFormatError):
            validate_ohlc_consistency(134.22, 136.50, 133.80, 138.00)