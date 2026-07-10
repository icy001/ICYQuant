from typing import Dict, Any
from datetime import datetime

from .exceptions import DataFormatError


def validate_bar_data(row: Dict[str, Any], required_columns: set = None) -> None:
    if required_columns is None:
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}

    missing = required_columns - set(row.keys())
    if missing:
        raise DataFormatError(f"Missing columns: {missing}")

    for col in ["open", "high", "low", "close", "volume"]:
        value = row.get(col)
        if value is None:
            raise DataFormatError(f"Missing value for {col}")
        try:
            float(value)
        except (ValueError, TypeError):
            raise DataFormatError(f"Invalid numeric value for {col}: {value}")

    timestamp = row.get("timestamp")
    if timestamp is None:
        raise DataFormatError("Missing timestamp")
    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        raise DataFormatError(f"Invalid timestamp format: {timestamp}")


def validate_ohlc_consistency(open_price: float, high: float, low: float, close: float) -> None:
    if high < low:
        raise DataFormatError(f"High ({high}) cannot be less than low ({low})")
    if open_price < low or open_price > high:
        raise DataFormatError(f"Open ({open_price}) outside range [{low}, {high}]")
    if close < low or close > high:
        raise DataFormatError(f"Close ({close}) outside range [{low}, {high}]")