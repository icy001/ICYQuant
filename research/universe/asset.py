from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class TradingSession:
    """Market trading session, expressed in the asset's local timezone.

    ``open`` / ``close`` are "HH:MM" strings. ``lunch_start`` / ``lunch_end``
    capture intraday breaks (e.g. A-shares / HKEX). A 24-hour market uses
    ``open="00:00"``, ``close="23:59"`` with ``rollover=True``.
    """

    open: str
    close: str
    lunch_start: Optional[str] = None
    lunch_end: Optional[str] = None
    rollover: bool = False  # session crosses midnight (e.g. SHFE night session)

    def __str__(self) -> str:
        if self.rollover:
            return f"{self.open}-{self.close} (rollover)"
        if self.lunch_start and self.lunch_end:
            return f"{self.open}-{self.close} break {self.lunch_start}-{self.lunch_end}"
        return f"{self.open}-{self.close}"


@dataclass(frozen=True, slots=True)
class Asset:
    symbol: str
    asset_type: str  # legacy: "stock" | "etf" | "index" | "fx" | "metals" | "futures"
    currency: str  # legacy: quote currency, e.g. "USD", "CNY", "HKD"
    asset_class: str = ""  # equity | fx | precious_metal | commodity
    region: str = ""  # US | CN | HK | GLOBAL
    exchange: str = ""  # NASDAQ | NYSE | SSE | HKEX | OTC | LME | SHFE ...
    timezone: str = "UTC"  # IANA name, e.g. America/New_York, Asia/Shanghai
    session: Optional[TradingSession] = None
    continuous_contract: bool = False  # True for AU/AG (main continuous futures)
    data_source: str = "synthetic"  # source of the research dataset
    description: str = ""

    def __post_init__(self) -> None:
        # Normalize missing optional fields so equality remains stable.
        if self.asset_class == "":
            object.__setattr__(self, "asset_class", self._default_class())
        if self.region == "":
            object.__setattr__(self, "region", self._default_region())

    def _default_class(self) -> str:
        type_to_class = {
            "stock": "equity",
            "etf": "equity",
            "index": "equity",
            "fx": "fx",
            "metals": "precious_metal",
            "futures": "commodity",
        }
        return type_to_class.get(self.asset_type, "other")

    def _default_region(self) -> str:
        type_to_region = {
            "stock": "US",
            "etf": "US",
            "fx": "GLOBAL",
            "metals": "GLOBAL",
            "futures": "CN",
        }
        return type_to_region.get(self.asset_type, "US")
