from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from research.data.bar import Bar


@dataclass(frozen=True)
class Event:
    timestamp: datetime


@dataclass(frozen=True)
class BarEvent(Event):
    symbol: str
    bar: Bar


@dataclass(frozen=True)
class SignalEvent(Event):
    symbol: str
    side: str
    quantity: float
    signal_id: str = ""


@dataclass(frozen=True)
class OrderEvent(Event):
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float = 0.0


@dataclass(frozen=True)
class FillEvent(Event):
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    cash_change: float