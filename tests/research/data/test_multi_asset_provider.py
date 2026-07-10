import pytest
from datetime import datetime
from unittest.mock import Mock

from research.data.bar import Bar
from research.data.universe import Universe
from research.data.snapshot import MarketSnapshot
from research.data.multi_asset_provider import MultiAssetDataProvider
from research.data.types import TimeFrame


class TestUniverse:

    def test_universe_creation(self):
        universe = Universe(["NVDA", "MSFT", "GLD"])
        assert universe.symbols == ["NVDA", "MSFT", "GLD"]

    def test_universe_contains(self):
        universe = Universe(["NVDA", "MSFT", "GLD"])
        assert universe.contains("NVDA") is True
        assert universe.contains("AAPL") is False

    def test_universe_length(self):
        universe = Universe(["NVDA", "MSFT", "GLD"])
        assert len(universe) == 3

    def test_universe_iteration(self):
        universe = Universe(["NVDA", "MSFT", "GLD"])
        symbols = list(universe)
        assert symbols == ["NVDA", "MSFT", "GLD"]


class TestMarketSnapshot:

    def test_market_snapshot_creation(self):
        nvda_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=160,
            high=165,
            low=158,
            close=165,
            volume=1000000
        )
        gld_bar = Bar(
            symbol="GLD",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=310,
            high=315,
            low=308,
            close=315,
            volume=500000
        )
        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 1, 1, 10, 0),
            bars={
                "NVDA": nvda_bar,
                "GLD": gld_bar
            }
        )
        assert snapshot.get("NVDA") == nvda_bar
        assert snapshot.get("GLD") == gld_bar

    def test_market_snapshot_get_nonexistent(self):
        nvda_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=160,
            high=165,
            low=158,
            close=165,
            volume=1000000
        )
        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 1, 1, 10, 0),
            bars={"NVDA": nvda_bar}
        )
        assert snapshot.get("GLD") is None

    def test_market_snapshot_symbols(self):
        nvda_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=160,
            high=165,
            low=158,
            close=165,
            volume=1000000
        )
        gld_bar = Bar(
            symbol="GLD",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=310,
            high=315,
            low=308,
            close=315,
            volume=500000
        )
        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 1, 1, 10, 0),
            bars={"NVDA": nvda_bar, "GLD": gld_bar}
        )
        symbols = snapshot.symbols()
        assert "NVDA" in symbols
        assert "GLD" in symbols
        assert len(symbols) == 2

    def test_market_snapshot_length(self):
        nvda_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=160,
            high=165,
            low=158,
            close=165,
            volume=1000000
        )
        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 1, 1, 10, 0),
            bars={"NVDA": nvda_bar}
        )
        assert len(snapshot) == 1


class TestMultiAssetDataProvider:

    def test_multi_asset_provider_initialization(self):
        providers = {"NVDA": Mock(), "GLD": Mock()}
        provider = MultiAssetDataProvider(providers)
        assert provider.providers == providers

    def test_multi_asset_provider_load(self):
        nvda_bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=160,
            high=165,
            low=158,
            close=165,
            volume=1000000
        )
        gld_bar = Bar(
            symbol="GLD",
            timestamp=datetime(2026, 1, 1, 10, 0),
            open=310,
            high=315,
            low=308,
            close=315,
            volume=500000
        )

        nvda_provider = Mock()
        nvda_provider.load_bars.return_value = [nvda_bar]

        gld_provider = Mock()
        gld_provider.load_bars.return_value = [gld_bar]

        providers = {"NVDA": nvda_provider, "GLD": gld_provider}
        multi_provider = MultiAssetDataProvider(providers)

        universe = Universe(["NVDA", "GLD"])
        datasets = multi_provider.load(universe, TimeFrame.D1)

        assert "NVDA" in datasets
        assert "GLD" in datasets
        assert datasets["NVDA"] == [nvda_bar]
        assert datasets["GLD"] == [gld_bar]

        nvda_provider.load_bars.assert_called_once()
        gld_provider.load_bars.assert_called_once()

    def test_multi_asset_provider_load_missing_symbol(self):
        providers = {"NVDA": Mock()}
        multi_provider = MultiAssetDataProvider(providers)
        universe = Universe(["NVDA", "GLD"])

        with pytest.raises(ValueError, match="No provider registered for symbol: GLD"):
            multi_provider.load(universe, TimeFrame.D1)

    def test_multi_asset_provider_register(self):
        providers = {"NVDA": Mock()}
        multi_provider = MultiAssetDataProvider(providers)

        gld_provider = Mock()
        multi_provider.register_provider("GLD", gld_provider)

        assert "GLD" in multi_provider.providers
        assert multi_provider.providers["GLD"] == gld_provider

    def test_multi_asset_provider_get(self):
        nvda_provider = Mock()
        providers = {"NVDA": nvda_provider}
        multi_provider = MultiAssetDataProvider(providers)

        assert multi_provider.get_provider("NVDA") == nvda_provider
        assert multi_provider.get_provider("GLD") is None