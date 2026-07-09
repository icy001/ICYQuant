import pandas as pd
from datetime import datetime
from typing import Optional

from .provider import MarketDataProvider


class ParquetProvider(MarketDataProvider):
    def __init__(self, data_dir: str = "data/"):
        self.data_dir = data_dir

    def load_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1D",
    ):
        filename = f"{self.data_dir}{symbol}.parquet"
        df = pd.read_parquet(filename)
        
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        
        mask = (df.index >= start) & (df.index <= end)
        df = df[mask]
        
        return df

    def load_tick_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ):
        filename = f"{self.data_dir}{symbol}_ticks.parquet"
        df = pd.read_parquet(filename)
        
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        
        mask = (df.index >= start) & (df.index <= end)
        df = df[mask]
        
        return df