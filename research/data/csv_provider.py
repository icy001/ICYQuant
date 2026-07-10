from pathlib import Path
import csv
from datetime import datetime
from typing import Optional

from .bar import Bar
from .provider import MarketDataProvider
from .types import TimeFrame
from .exceptions import SymbolNotFoundError, DataFormatError
from .validators import validate_bar_data, validate_ohlc_consistency


class CsvMarketDataProvider(MarketDataProvider):

    def __init__(self, data_root: Path):
        self._data_root = data_root

    def load_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Bar]:

        filename = self._data_root / f"{symbol}_{timeframe.value}.csv"

        if not filename.exists():
            raise SymbolNotFoundError(f"File not found: {filename}")

        bars: list[Bar] = []

        with filename.open("r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
            if not required_columns.issubset(set(reader.fieldnames or [])):
                raise DataFormatError(
                    f"CSV missing required columns. Expected: {required_columns}"
                )

            for row in reader:
                validate_bar_data(row)

                timestamp = datetime.fromisoformat(row["timestamp"])

                if start is not None and timestamp < start:
                    continue
                if end is not None and timestamp > end:
                    continue

                open_price = float(row["open"])
                high = float(row["high"])
                low = float(row["low"])
                close = float(row["close"])
                volume = float(row["volume"])

                validate_ohlc_consistency(open_price, high, low, close)

                bar = Bar(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )

                bars.append(bar)

        return bars