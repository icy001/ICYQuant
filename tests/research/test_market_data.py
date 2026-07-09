import pandas as pd
import pytest
from datetime import datetime
import os

from research.data.csv_provider import CSVProvider
from research.data.parquet_provider import ParquetProvider


class TestMarketData:
    @pytest.fixture
    def test_data_dir(self):
        return "tests/research/data/"

    @pytest.fixture
    def sample_data(self, test_data_dir):
        os.makedirs(test_data_dir, exist_ok=True)
        
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        data = {
            "datetime": dates,
            "open": 450 + pd.Series(range(100)) * 2,
            "high": 455 + pd.Series(range(100)) * 2,
            "low": 445 + pd.Series(range(100)) * 2,
            "close": 450 + pd.Series(range(100)) * 2,
            "volume": 1000000 + pd.Series(range(100)) * 10000,
        }
        df = pd.DataFrame(data)
        
        csv_path = f"{test_data_dir}NVDA.csv"
        df.to_csv(csv_path, index=False)
        
        parquet_path = f"{test_data_dir}NVDA.parquet"
        df.to_parquet(parquet_path, index=False)
        
        yield test_data_dir
        
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(parquet_path):
            os.remove(parquet_path)

    def test_csv_provider_load_bars(self, sample_data):
        provider = CSVProvider(data_dir=sample_data)
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        
        df = provider.load_bars("NVDA", start, end)
        
        assert len(df) == 91
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert df.index.name == "datetime"

    def test_parquet_provider_load_bars(self, sample_data):
        provider = ParquetProvider(data_dir=sample_data)
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        
        df = provider.load_bars("NVDA", start, end)
        
        assert len(df) == 91
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert df.index.name == "datetime"

    def test_data_range_filtering(self, sample_data):
        provider = CSVProvider(data_dir=sample_data)
        
        start = datetime(2024, 2, 1)
        end = datetime(2024, 2, 29)
        
        df = provider.load_bars("NVDA", start, end)
        
        assert len(df) == 29
        assert df.index[0].month == 2
        assert df.index[-1].month == 2