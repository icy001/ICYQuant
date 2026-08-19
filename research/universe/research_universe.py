"""Research Universe v1.1 — the nine core research assets.

Universe layout (research dimensions):

    Equity
    ├── NVDA       US   NASDAQ       high-growth / high-vol
    ├── SPY        US   NYSE         broad market trend
    ├── QQQ        US   NASDAQ       tech trend
    ├── 000688.SH  CN   SSE          China STAR 50 (tech growth)
    └── HSTECH     HK   HKEX         Hang Seng Tech (CN internet/tech)

    FX
    └── EURUSD     GLOBAL            trend / range

    Precious Metals
    ├── XAUUSD     GLOBAL            London Gold
    ├── AU         CN   SHFE         Shanghai Gold futures (continuous)
    └── AG         CN   SHFE         Shanghai Silver futures (continuous)

The precious-metal trio (XAUUSD / AU / AG) is intentionally kept so that
Strategy Discovery can test whether a strategy is pricing-system specific
or globally robust across London Gold and China futures precious metals.
"""
from __future__ import annotations

from .asset import Asset, TradingSession

# --- Trading sessions (asset-local time, IANA timezone) --------------------

US_SESSION = TradingSession(open="09:30", close="16:00")          # Mon-Fri
CN_SESSION = TradingSession(open="09:30", close="15:00",
                            lunch_start="11:30", lunch_end="13:00")
HK_SESSION = TradingSession(open="09:30", close="16:00",
                            lunch_start="12:00", lunch_end="13:00")
FX_SESSION = TradingSession(open="00:00", close="23:59", rollover=True)  # 24h
XAU_SESSION = TradingSession(open="00:00", close="23:59", rollover=True)  # near-24h
SHFE_SESSION = TradingSession(open="09:00", close="15:00",
                              lunch_start="11:30", lunch_end="13:00")
SHFE_NIGHT = TradingSession(open="21:00", close="02:30",
                            lunch_start=None, lunch_end=None, rollover=True)

RESEARCH_UNIVERSE_V1_1: tuple[Asset, ...] = (
    Asset(
        symbol="NVDA",
        asset_type="stock",
        currency="USD",
        asset_class="equity",
        region="US",
        exchange="NASDAQ",
        timezone="America/New_York",
        session=US_SESSION,
        data_source="synthetic",
        description="NVIDIA Corp — US high-growth / high-volatility equity",
    ),
    Asset(
        symbol="SPY",
        asset_type="etf",
        currency="USD",
        asset_class="equity",
        region="US",
        exchange="NYSE",
        timezone="America/New_York",
        session=US_SESSION,
        data_source="synthetic",
        description="SPDR S&P 500 ETF — broad US market trend",
    ),
    Asset(
        symbol="QQQ",
        asset_type="etf",
        currency="USD",
        asset_class="equity",
        region="US",
        exchange="NASDAQ",
        timezone="America/New_York",
        session=US_SESSION,
        data_source="synthetic",
        description="Invesco QQQ — US technology trend",
    ),
    Asset(
        symbol="000688.SH",
        asset_type="index",
        currency="CNY",
        asset_class="equity",
        region="CN",
        exchange="SSE",
        timezone="Asia/Shanghai",
        session=CN_SESSION,
        data_source="synthetic",
        description="SSE STAR 50 Index — China technology growth",
    ),
    Asset(
        symbol="HSTECH",
        asset_type="index",
        currency="HKD",
        asset_class="equity",
        region="HK",
        exchange="HKEX",
        timezone="Asia/Hong_Kong",
        session=HK_SESSION,
        data_source="synthetic",
        description="Hang Seng TECH Index — CN internet / technology growth",
    ),
    Asset(
        symbol="EURUSD",
        asset_type="fx",
        currency="USD",
        asset_class="fx",
        region="GLOBAL",
        exchange="OTC",
        timezone="Etc/UTC",
        session=FX_SESSION,
        data_source="synthetic",
        description="Euro / US Dollar spot — trend / range FX",
    ),
    Asset(
        symbol="XAUUSD",
        asset_type="metals",
        currency="USD",
        asset_class="precious_metal",
        region="GLOBAL",
        exchange="OTC",
        timezone="Etc/UTC",
        session=XAU_SESSION,
        data_source="synthetic",
        description="London Gold spot — global gold / macro",
    ),
    Asset(
        symbol="AU",
        asset_type="futures",
        currency="CNY",
        asset_class="precious_metal",
        region="CN",
        exchange="SHFE",
        timezone="Asia/Shanghai",
        session=SHFE_SESSION,
        continuous_contract=True,
        data_source="synthetic",
        description="SHFE Gold futures (AU0 continuous main contract) — China gold futures",
    ),
    Asset(
        symbol="AG",
        asset_type="futures",
        currency="CNY",
        asset_class="precious_metal",
        region="CN",
        exchange="SHFE",
        timezone="Asia/Shanghai",
        session=SHFE_SESSION,
        continuous_contract=True,
        data_source="synthetic",
        description="SHFE Silver futures (AG0 continuous main contract) — China silver futures",
    ),
)


def by_symbol(symbol: str) -> Asset:
    """Return the Asset for ``symbol``; raise KeyError if unknown."""
    for asset in RESEARCH_UNIVERSE_V1_1:
        if asset.symbol == symbol:
            return asset
    raise KeyError(f"Unknown research universe symbol: {symbol!r}")


def by_class(asset_class: str) -> tuple[Asset, ...]:
    """Return all assets in a class: equity | fx | precious_metal."""
    return tuple(a for a in RESEARCH_UNIVERSE_V1_1 if a.asset_class == asset_class)


def symbols() -> list[str]:
    return [a.symbol for a in RESEARCH_UNIVERSE_V1_1]
