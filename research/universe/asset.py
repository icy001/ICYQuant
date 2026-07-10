from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asset:
    symbol: str
    asset_type: str
    currency: str