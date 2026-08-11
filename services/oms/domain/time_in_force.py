"""TimeInForce enum."""
from __future__ import annotations

from enum import Enum, auto


class TimeInForce(Enum):
    DAY = auto()
    GTC = auto()
    IOC = auto()
    FOK = auto()
    GTD = auto()

    @property
    def label(self) -> str:
        _labels = {
            TimeInForce.DAY: "Day",
            TimeInForce.GTC: "Good-Till-Cancelled",
            TimeInForce.IOC: "Immediate-Or-Cancel",
            TimeInForce.FOK: "Fill-Or-Kill",
            TimeInForce.GTD: "Good-Till-Date",
        }
        return _labels[self]

    @property
    def is_immediate(self) -> bool:
        return self in (TimeInForce.IOC, TimeInForce.FOK)
