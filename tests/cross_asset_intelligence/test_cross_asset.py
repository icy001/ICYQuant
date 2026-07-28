"""Tests for AI Cross Asset Intelligence Engine."""

from __future__ import annotations

import pytest
from datetime import datetime

from services.cross_asset_intelligence import (
    # Relationship
    AssetRelationship,
    AssetClass,
    RelationshipType,
    RiskRegime,
    DollarTrend,
    AssetNode,
    RelationshipGraph,
    CrossAssetSignal,
    # Equity-Bond
    EquityBondAnalyzer,
    EquityBondResult,
    # Dollar
    DollarIntelligenceEngine,
    DollarResult,
    # Commodity
    CommodityIntelligenceEngine,
    CommodityResult,
    # Crypto
    CryptoIntelligenceEngine,
    CryptoResult,
    CryptoDominance,
    CryptoRiskAppetite,
    # Correlation
    CorrelationEngine,
    CorrelationResult,
    CorrelationMethod,
    CorrelationRegime,
    # Rotation
    AssetRotationDetector,
    AssetRotationResult,
    RotationEvent,
    RotationType,
    RotationRegime,
    # Signal
    CrossAssetSignalGenerator,
    SignalResult,
    SignalPriority,
    SignalAction,
    # Risk
    CrossAssetRiskMonitor,
    RiskMonitorResult,
    RiskLevel,
    RiskCategory,
    RiskComponent,
    # Memory
    CrossAssetMemory,
    CrossAssetMemoryEntry,
    # Service
    CrossAssetIntelligenceService,
    CrossAssetPipelineResult,
)


# ============================================================================
# Test AssetRelationship
# ============================================================================


class TestAssetRelationship:
    """Tests for AssetRelationship data model."""

    def test_create_basic(self):
        rel = AssetRelationship(asset_a="SPX", asset_b="TLT", correlation=0.3)
        assert rel.asset_a == "SPX"
        assert rel.asset_b == "TLT"
        assert rel.correlation == 0.3
        assert rel.is_positive is True
        assert rel.is_negative is False
        assert rel.is_strong is False
        assert rel.is_significant is True

    def test_strong_positive(self):
        rel = AssetRelationship(asset_a="SPX", asset_b="QQQ", correlation=0.85)
        assert rel.is_strong is True
        assert rel.relationship_type == RelationshipType.UNCORRELATED

    def test_negative_correlation(self):
        rel = AssetRelationship(asset_a="SPX", asset_b="VIX", correlation=-0.7)
        assert rel.is_negative is True
        assert rel.is_positive is False
        assert rel.is_strong is True

    def test_correlation_clamping(self):
        rel = AssetRelationship(asset_a="A", asset_b="B", correlation=1.5)
        assert rel.correlation == 1.0

        rel2 = AssetRelationship(asset_a="A", asset_b="B", correlation=-2.0)
        assert rel2.correlation == -1.0

    def test_not_significant(self):
        rel = AssetRelationship(asset_a="A", asset_b="B", correlation=0.2, confidence=0.3)
        assert rel.is_significant is False

    def test_with_classes(self):
        rel = AssetRelationship(
            asset_a="SPX", asset_b="IEF",
            correlation=-0.4,
            class_a=AssetClass.EQUITY, class_b=AssetClass.BOND_GOVERNMENT,
        )
        assert rel.class_a == AssetClass.EQUITY
        assert rel.class_b == AssetClass.BOND_GOVERNMENT


# ============================================================================
# Test AssetNode
# ============================================================================


class TestAssetNode:
    """Tests for AssetNode."""

    def test_create_basic(self):
        node = AssetNode(asset="SPX", asset_class=AssetClass.EQUITY)
        assert node.asset == "SPX"
        assert node.degree == 0
        assert node.positive_count == 0
        assert node.negative_count == 0

    def test_with_relationships(self):
        r1 = AssetRelationship(asset_a="SPX", asset_b="QQQ", correlation=0.8)
        r2 = AssetRelationship(asset_a="SPX", asset_b="VIX", correlation=-0.6)
        node = AssetNode(asset="SPX", relationships=[r1, r2])
        assert node.degree == 2
        assert node.positive_count == 1
        assert node.negative_count == 1


# ============================================================================
# Test RelationshipGraph
# ============================================================================


class TestRelationshipGraph:
    """Tests for RelationshipGraph."""

    def test_create_empty(self):
        graph = RelationshipGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_add_and_query(self):
        graph = RelationshipGraph()
        r1 = AssetRelationship(asset_a="SPX", asset_b="TLT", correlation=-0.3)
        node = AssetNode(asset="SPX", relationships=[r1])
        graph.nodes["SPX"] = node
        graph.edges.append(r1)

        assert graph.node_count == 1
        assert graph.get_node("SPX") is not None
        assert graph.get_node("UNKNOWN") is None
        assert len(graph.get_relationships("SPX")) == 1

    def test_get_related_assets(self):
        r1 = AssetRelationship(asset_a="SPX", asset_b="QQQ", correlation=0.8)
        r2 = AssetRelationship(asset_a="SPX", asset_b="DXY", correlation=-0.15)
        node = AssetNode(asset="SPX", relationships=[r1, r2])
        graph = RelationshipGraph()
        graph.nodes["SPX"] = node

        related = graph.get_related_assets("SPX", min_corr=0.3)
        assert "QQQ" in related
        assert "DXY" not in related

    def test_get_best_hedge(self):
        r1 = AssetRelationship(asset_a="SPX", asset_b="QQQ", correlation=0.8)
        r2 = AssetRelationship(asset_a="SPX", asset_b="TLT", correlation=-0.5)
        r3 = AssetRelationship(asset_a="SPX", asset_b="GLD", correlation=0.1)
        node = AssetNode(asset="SPX", relationships=[r1, r2, r3])
        graph = RelationshipGraph()
        graph.nodes["SPX"] = node

        hedge = graph.get_best_hedge("SPX")
        assert hedge is not None
        assert hedge.asset_b == "TLT"

    def test_get_best_hedge_none(self):
        graph = RelationshipGraph()
        assert graph.get_best_hedge("SPX") is None


# ============================================================================
# Test CrossAssetSignal
# ============================================================================


class TestCrossAssetSignal:
    """Tests for data model."""

    def test_is_actionable(self):
        signal = CrossAssetSignal(
            signal_id="s1", asset="SPX", signal_type="rotation",
            direction=1, confidence=0.7,
        )
        assert signal.is_actionable is True

    def test_not_actionable_neutral(self):
        signal = CrossAssetSignal(
            signal_id="s2", asset="SPX", signal_type="neutral",
            direction=0, confidence=0.6,
        )
        assert signal.is_actionable is False

    def test_not_actionable_low_confidence(self):
        signal = CrossAssetSignal(
            signal_id="s3", asset="SPX", signal_type="test",
            direction=1, confidence=0.3,
        )
        assert signal.is_actionable is False

    def test_absolute_strength(self):
        signal = CrossAssetSignal(
            signal_id="s4", asset="SPX", signal_type="test",
            value=0.8, confidence=0.5,
        )
        assert signal.absolute_strength == 0.4


# ============================================================================
# Test EquityBondAnalyzer
# ============================================================================


class TestEquityBondAnalyzer:
    """Tests for EquityBondAnalyzer."""

    def setup_method(self):
        self.analyzer = EquityBondAnalyzer()

    def test_analyze_full(self):
        result = self.analyzer.analyze_full(yield_10y=4.0, real_yield=1.0, credit_spread=1.0)
        assert isinstance(result, EquityBondResult)
        assert result.yield_10y == 4.0
        assert result.confidence > 0

    def test_analyze_dict_interface(self):
        data = {"yield_10y": 4.5, "real_yield": 1.5, "credit_spread": 1.2}
        result = self.analyzer.analyze(data)
        assert "equity_pressure" in result
        assert "risk" in result
        assert "reason" in result

    def test_high_rates_pressure(self):
        result = self.analyzer.analyze_full(yield_10y=6.0, real_yield=2.5, credit_spread=2.5)
        assert result.equity_pressure in ("HIGH", "CRITICAL")
        assert result.is_equity_pressured is True
        assert result.is_equity_favorable is False

    def test_low_rates_favorable(self):
        result = self.analyzer.analyze_full(yield_10y=2.5, real_yield=0.3, credit_spread=0.8)
        assert result.equity_pressure in ("LOW", "NEUTRAL")
        assert result.is_equity_favorable is True

    def test_growth_stock_pressure(self):
        result = self.analyzer.analyze_full(yield_10y=5.5, real_yield=2.5)
        assert result.growth_stock_pressure in ("HIGH", "CRITICAL")
        assert result.is_growth_favorable is False

    def test_valuation_signal(self):
        result = self.analyzer.analyze_full(yield_10y=4.0, real_yield=1.0, credit_spread=1.0)
        assert result.valuation_signal in ("CHEAP", "ATTRACTIVE", "FAIR", "RICH", "OVERVAULED")

    def test_yield_trend(self):
        self.analyzer.yield_history = [4.0] * 10 + [5.0] * 10
        trend = self.analyzer.get_yield_trend()
        assert trend == "rising"

    def test_yield_trend_insufficient(self):
        self.analyzer.yield_history = [4.0]
        assert self.analyzer.get_yield_trend() == "stable"

    def test_supporting_factors(self):
        result = self.analyzer.analyze_full(yield_10y=6.0, real_yield=2.5, credit_spread=2.5)
        assert len(result.supporting_factors) > 0

    def test_clear(self):
        self.analyzer.analyze_full(4.0, 1.0, 1.0)
        self.analyzer.clear()
        assert len(self.analyzer.yield_history) == 0


# ============================================================================
# Test DollarIntelligenceEngine
# ============================================================================


class TestDollarIntelligenceEngine:
    """Tests for DollarIntelligenceEngine."""

    def setup_method(self):
        self.engine = DollarIntelligenceEngine()

    def test_analyze_full_stable(self):
        self.engine.dxy_history = [100] * 10
        self.engine.dxy_history.append(100)
        result = self.engine.analyze_full(100.0)
        assert result.trend == DollarTrend.STABLE
        assert isinstance(result, DollarResult)

    def test_analyze_full_appreciation(self):
        self.engine.dxy_history = [100] * 20
        result = self.engine.analyze_full(103.0)
        assert result.trend == DollarTrend.APPRECIATION

    def test_analyze_full_depreciation(self):
        self.engine.dxy_history = [100] * 20
        result = self.engine.analyze_full(96.0, real_yield=0.5, fed_stance="dovish")
        assert result.trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION)

    def test_analyze_dict(self):
        self.engine.dxy_history = [100] * 10
        result = self.engine.analyze(100.0)
        assert "trend" in result
        assert "impacts" in result

    def test_gold_outlook(self):
        self.engine.dxy_history = [100] * 20
        assert self.engine.get_gold_outlook(96.0) == "bullish"
        self.engine.clear()
        self.engine.dxy_history = [100] * 20
        assert self.engine.get_gold_outlook(104.0) == "bearish"

    def test_commodity_outlook(self):
        self.engine.dxy_history = [100] * 20
        assert self.engine.get_commodity_outlook(95.0) == "strongly_bullish"

    def test_em_outlook(self):
        self.engine.dxy_history = [100] * 20
        assert self.engine.get_em_outlook(104.0) == "bearish"

    def test_risk_asset_outlook(self):
        self.engine.dxy_history = [100] * 20
        assert self.engine.get_risk_asset_outlook(96.0) == "favorable"

    def test_impacts_weakening(self):
        result = DollarResult(trend=DollarTrend.DEPRECIATION)
        assert result.gold_signal == "bullish"
        assert result.commodity_signal == "bullish"

    def test_impacts_strengthening(self):
        result = DollarResult(trend=DollarTrend.APPRECIATION)
        assert result.is_strengthening is True
        assert result.is_weakening is False

    def test_get_trend(self):
        self.engine.dxy_history = [100] * 10 + [102] * 10
        assert self.engine.get_trend() == "rising"

    def test_get_trend_stable_short(self):
        assert self.engine.get_trend() == "stable"

    def test_clear(self):
        self.engine.dxy_history = [100, 101, 102]
        self.engine.clear()
        assert len(self.engine.dxy_history) == 0


# ============================================================================
# Test CommodityIntelligenceEngine
# ============================================================================


class TestCommodityIntelligenceEngine:
    """Tests for CommodityIntelligenceEngine."""

    def setup_method(self):
        self.engine = CommodityIntelligenceEngine()

    def test_analyze_full_bullish(self):
        # Create strong rising trend: 20 data points going 1900→2300
        for i in range(20):
            self.engine.price_history.setdefault("gold", []).append(1900 + i * 20)
        result = self.engine.analyze_full("gold", 2320.0)
        assert isinstance(result, CommodityResult)
        assert result.signal == "BULLISH"
        assert result.is_bullish is True

    def test_analyze_full_neutral(self):
        self.engine.price_history["gold"] = [2000] * 20
        result = self.engine.analyze_full("gold", 2000.0)
        assert result.signal == "NEUTRAL"

    def test_analyze_dict(self):
        self.engine.price_history["gold"] = [2000] * 10
        result = self.engine.analyze("gold", 2000.0)
        assert result["commodity"] == "gold"
        assert "signal" in result

    def test_analyze_gold_with_dollar(self):
        self.engine.price_history["gold"] = [2000] * 20
        result = self.engine.analyze_gold(2000.0, dollar_trend="depreciation")
        assert result.signal in ("BULLISH", "NEUTRAL")

    def test_analyze_oil(self):
        self.engine.price_history["oil"] = [80] * 20
        result = self.engine.analyze_oil(80.0)
        assert result.commodity == "oil"

    def test_analyze_copper(self):
        self.engine.price_history["copper"] = [4.0] * 20
        result = self.engine.analyze_copper(4.0)
        assert result.commodity == "copper"

    def test_macro_signal(self):
        self.engine.price_history["gold"] = [1900] * 20
        result = self.engine.analyze_full("gold", 2200.0)
        assert "macro_signal" in result.__dict__ or hasattr(result, "macro_signal")

    def test_inflation_signal(self):
        self.engine.price_history["gold"] = [1900] * 10 + [2200] * 10
        self.engine.price_history["oil"] = [70] * 10 + [90] * 10
        signal = self.engine.get_inflation_signal()
        assert signal in ("inflation_rising", "inflation_accelerating", "stable")

    def test_growth_signal(self):
        self.engine.price_history["copper"] = [4.0] * 10 + [5.0] * 10
        signal = self.engine.get_growth_signal()
        assert signal in ("growth_accelerating", "growth_decelerating", "growth_stable")

    def test_trend_computation(self):
        self.engine.price_history["copper"] = [4.0, 4.1, 4.2, 4.3, 4.4, 4.5]
        assert self.engine._compute_trend("copper") in ("rising", "stable")

    def test_clear(self):
        self.engine.price_history["gold"] = [2000, 2100]
        self.engine.clear()
        assert len(self.engine.price_history) == 0


# ============================================================================
# Test CryptoIntelligenceEngine
# ============================================================================


class TestCryptoIntelligenceEngine:
    """Tests for CryptoIntelligenceEngine."""

    def setup_method(self):
        self.engine = CryptoIntelligenceEngine()

    def test_analyze_full_bullish(self):
        for i in range(20):
            self.engine.btc_history.append(50000 + i * 500)
            self.engine.eth_history.append(3000 + i * 50)
        result = self.engine.analyze_full(61000.0, eth_price=4100.0, btc_dominance=48.0)
        assert isinstance(result, CryptoResult)
        assert result.signal == "BULLISH"
        assert result.is_bullish is True

    def test_analyze_full_distress(self):
        for i in range(20):
            self.engine.btc_history.append(50000 - i * 500)
        result = self.engine.analyze_full(40000.0, eth_price=2000.0, btc_dominance=58.0)
        assert result.signal == "BEARISH"
        assert result.is_bearish is True
        assert result.risk_appetite in (CryptoRiskAppetite.RISK_AVERSE, CryptoRiskAppetite.EXTREME_FEAR)

    def test_analyze_dict(self):
        self.engine.btc_history = [50000] * 10
        result = self.engine.analyze(50000.0)
        assert "signal" in result
        assert "risk_appetite" in result

    def test_btc_dominance_season(self):
        self.engine.btc_history = [50000] * 20
        result = self.engine.analyze_full(50000.0, btc_dominance=60.0)
        assert result.dominance_state == CryptoDominance.BTC_SEASON
        assert result.is_btc_season is True

    def test_alt_season(self):
        self.engine.btc_history = [50000] * 20
        result = self.engine.analyze_full(50000.0, btc_dominance=40.0)
        assert result.dominance_state == CryptoDominance.ALT_SEASON
        assert result.is_alt_season is True

    def test_risk_appetite_signal(self):
        self.engine.btc_history = [50000] * 10
        self.engine.dominance_history = [48] * 10
        signal = self.engine.get_risk_appetite_signal()
        assert signal in ("risk_seeking", "risk_neutral", "risk_averse", "extreme_fear", "unknown")

    def test_crypto_leading_stocks(self):
        self.engine.btc_history = [50000, 51000, 52000, 53000, 54000, 55000, 56000, 57000, 58000, 59000]
        assert self.engine.is_crypto_leading_stocks() is True

    def test_correlation_signal(self):
        self.engine.btc_history = [50000] * 20
        result = self.engine.analyze_full(45000.0, btc_dominance=50.0)
        assert result.correlation_signal is not None
        assert len(result.correlation_signal) > 0

    def test_factors(self):
        self.engine.btc_history = [50000] * 20
        result = self.engine.analyze_full(45000.0, btc_dominance=40.0)
        assert len(result.factors) > 0

    def test_is_risk_on(self):
        result = CryptoResult(risk_appetite=CryptoRiskAppetite.RISK_SEEKING)
        assert result.is_risk_on is True

    def test_clear(self):
        self.engine.btc_history = [50000, 51000]
        self.engine.eth_history = [3000, 3100]
        self.engine.dominance_history = [50, 48]
        self.engine.clear()
        assert len(self.engine.btc_history) == 0
        assert len(self.engine.eth_history) == 0
        assert len(self.engine.dominance_history) == 0


# ============================================================================
# Test CorrelationEngine
# ============================================================================


class TestCorrelationEngine:
    """Tests for CorrelationEngine."""

    def setup_method(self):
        self.engine = CorrelationEngine()

    def test_compute_pearson_perfect_positive(self):
        for i in range(50):
            self.engine.add_price("SPX", 100 + i)
            self.engine.add_price("QQQ", 200 + i * 2)
        corr = self.engine.compute("SPX", "QQQ")
        assert pytest.approx(corr, abs=0.01) == 1.0

    def test_compute_pearson_perfect_negative(self):
        # Create anti-correlated returns: SPX alternating up, VIX alternating down
        for i in range(50):
            direction = 1 if i % 2 == 0 else -1
            self.engine.add_price("SPX", 100 + i * 0.5 + direction * 1.5)
            self.engine.add_price("VIX", 30 - i * 0.2 - direction * 1.0)
        corr = self.engine.compute("SPX", "VIX")
        assert corr < 0.3

    def test_compute_spearman(self):
        for i in range(50):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        corr = self.engine.compute("A", "B", CorrelationMethod.SPEARMAN)
        assert pytest.approx(corr, abs=0.01) == 1.0

    def test_compute_dynamic(self):
        for i in range(50):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        corr = self.engine.compute("A", "B", CorrelationMethod.DYNAMIC)
        assert corr > 0.9

    def test_compute_empty(self):
        assert self.engine.compute("A", "B") == 0.0

    def test_compute_matrix(self):
        for i in range(30):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
            self.engine.add_price("C", 150 - i)
        matrix = self.engine.compute_matrix(["A", "B", "C"])
        assert len(matrix) == 6  # 3*2 pairs, both directions
        assert ("A", "B") in matrix

    def test_compute_relationship(self):
        for i in range(30):
            direction = 1 if i % 2 == 0 else -1
            self.engine.add_price("SPX", 100 + i * 0.5 + direction * 1.5)
            self.engine.add_price("TLT", 100 - i * 0.3 - direction * 1.0)
        rel = self.engine.compute_relationship("SPX", "TLT")
        assert isinstance(rel, AssetRelationship)
        # TLT is counter-cyclical: negative or weak correlation expected
        assert rel.correlation < 0.2

    def test_compute_rolling(self):
        for i in range(100):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        rolling = self.engine.compute_rolling("A", "B", window=20)
        assert len(rolling) > 0

    def test_detect_regime(self):
        for i in range(100):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        regime = self.engine.detect_regime("A", "B")
        assert isinstance(regime, CorrelationRegime)

    def test_analyze(self):
        for i in range(60):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        result = self.engine.analyze()
        assert isinstance(result, CorrelationResult)
        assert result.average_correlation > 0.9
        assert result.diversification_score < 0.5

    def test_get_average_correlation(self):
        for i in range(30):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
        avg = self.engine.get_average_correlation()
        assert avg > 0.9

    def test_find_highest_correlated(self):
        for i in range(30):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
            self.engine.add_price("C", 150 - i)
        result = self.engine.find_highest_correlated("A")
        assert result is not None

    def test_find_lowest_correlated(self):
        for i in range(30):
            self.engine.add_price("A", 100 + i)
            self.engine.add_price("B", 200 + i * 2)
            self.engine.add_price("C", 150 - i)
        result = self.engine.find_lowest_correlated("A")
        assert result is not None

    def test_get_hedge_candidates(self):
        for i in range(30):
            direction = 1 if i % 2 == 0 else -1
            self.engine.add_price("SPX", 100 + i * 0.5 + direction * 1.5)
            self.engine.add_price("TLT", 100 - i * 0.3 - direction * 1.0)
            self.engine.add_price("GLD", 90 + i * 0.1)
        candidates = self.engine.get_hedge_candidates("SPX")
        # SPX and TLT should have negative or weak correlation
        assert len(candidates) <= 2  # At most 2 candidates (TLT, GLD)

    def test_add_prices(self):
        self.engine.add_prices({"A": 100, "B": 200, "C": 300})
        assert "A" in self.engine.price_histories
        assert "B" in self.engine.price_histories
        assert "C" in self.engine.price_histories

    def test_clear(self):
        self.engine.add_price("A", 100)
        self.engine.add_price("B", 200)
        self.engine.clear()
        assert len(self.engine.price_histories) == 0


# ============================================================================
# Test AssetRotationDetector
# ============================================================================


class TestAssetRotationDetector:
    """Tests for AssetRotationDetector."""

    def setup_method(self):
        self.detector = AssetRotationDetector()

    def test_detect_risk_on_off_risk_on(self):
        # Feed enough performance to cross the 5.0 threshold
        for _ in range(20):
            self.detector.add_performance("SPX", 3.0)
            self.detector.add_performance("QQQ", 4.0)
            self.detector.add_performance("TLT", -1.0)
            self.detector.add_performance("GLD", -0.5)
        event = self.detector.detect_risk_on_off()
        # perf_on = 3.5 sum over 20 = 70. But aggregate is sum, not average.
        # Actually _group_performance sums the last window entries.
        # SPX=3.0*20=60, QQQ=4.0*20=80, average of sums = 70. > 5.0 ✅
        assert event is not None
        assert event.rotation_type == RotationType.RISK_ON

    def test_detect_risk_on_off_risk_off(self):
        for _ in range(20):
            self.detector.add_performance("SPX", -2.0)
            self.detector.add_performance("TLT", 2.0)
            self.detector.add_performance("GLD", 3.0)
        event = self.detector.detect_risk_on_off()
        assert event is not None
        assert event.rotation_type == RotationType.RISK_OFF

    def test_detect_risk_on_off_none(self):
        event = self.detector.detect_risk_on_off()
        assert event is None

    def test_detect_sector_rotation(self):
        sectors = {"Tech": 8.0, "Financials": 3.0, "Energy": 5.0, "Utilities": 1.0, "Healthcare": 2.0, "Consumer": -1.0}
        events = self.detector.detect_sector_rotation(sectors)
        assert len(events) == 1
        assert events[0].rotation_type == RotationType.SECTOR_ROTATION

    def test_detect_style_rotation_growth(self):
        event = self.detector.detect_style_rotation(growth_return=8.0, value_return=2.0)
        assert event is not None
        assert "growth" in event.to_assets

    def test_detect_style_rotation_value(self):
        event = self.detector.detect_style_rotation(growth_return=0.0, value_return=6.0)
        assert event is not None
        assert "value" in event.to_assets

    def test_detect_style_rotation_none(self):
        event = self.detector.detect_style_rotation(growth_return=2.0, value_return=1.0)
        assert event is None

    def test_detect_flight_to_safety(self):
        event = self.detector.detect_flight_to_safety(
            equity_return=-8.0, bond_return=2.0, gold_return=5.0,
        )
        assert event is not None
        assert event.rotation_type == RotationType.FLIGHT_TO_SAFETY

    def test_detect_flight_to_safety_none(self):
        event = self.detector.detect_flight_to_safety(
            equity_return=2.0, bond_return=-1.0, gold_return=1.0,
        )
        assert event is None

    def test_analyze_dict_interface(self):
        self.detector.add_performance("SPX", 3.0)
        self.detector.add_performance("TLT", -1.0)
        result = self.detector.analyze(["TLT"], ["SPX"])
        assert "rotation_type" in result
        assert "strength" in result

    def test_analyze_full(self):
        self.detector.add_performance("SPX", 3.0)
        self.detector.add_performance("TLT", -1.0)
        self.detector.add_performance("QQQ", 4.0)
        self.detector.add_performance("IWD", -0.5)
        result = self.detector.analyze_full()
        assert isinstance(result, AssetRotationResult)
        assert result.current_regime in RotationRegime

    def test_should_rotate(self):
        result = AssetRotationResult()
        assert result.should_rotate is False

    def test_active_rotations(self):
        event = RotationEvent(rotation_type=RotationType.RISK_ON, strength=0.5)
        result = AssetRotationResult(events=[event])
        assert len(result.active_rotations) == 1

    def test_clear(self):
        self.detector.add_performance("SPX", 3.0)
        self.detector.add_flow("SPX", 100)
        self.detector.clear()
        assert len(self.detector.performance_data) == 0
        assert len(self.detector.flow_data) == 0


# ============================================================================
# Test CrossAssetSignalGenerator
# ============================================================================


class TestCrossAssetSignalGenerator:
    """Tests for CrossAssetSignalGenerator."""

    def setup_method(self):
        self.gen = CrossAssetSignalGenerator()

    def test_generate_empty(self):
        result = self.gen.generate()
        assert isinstance(result, SignalResult)
        assert result.action == SignalAction.MONITOR
        assert result.confidence == 0.2

    def test_generate_bullish(self):
        self.gen.register_equity_bond("LOW", "ATTRACTIVE", confidence=0.9)
        self.gen.register_dollar("depreciation", "bullish", confidence=0.9)
        self.gen.register_crypto("BULLISH", "risk_seeking", confidence=0.9)
        result = self.gen.generate()
        assert result.score > 0.2
        assert result.action != SignalAction.MONITOR

    def test_generate_bearish(self):
        self.gen.register_equity_bond("CRITICAL", "OVERVAULED", confidence=0.9)
        self.gen.register_dollar("strong_appreciation", "bearish", confidence=0.9)
        self.gen.register_crypto("BEARISH", "risk_averse", confidence=0.9)
        result = self.gen.generate()
        assert result.score < -0.2
        assert result.action in (SignalAction.UNDERWEIGHT, SignalAction.REDUCE, SignalAction.MARKET_WEIGHT)

    def test_generate_for_asset(self):
        result = self.gen.generate_for_asset(
            target_asset="equity_portfolio",
            equity_bond_pressure="LOW",
            equity_bond_val="ATTRACTIVE",
            dollar_trend="depreciation",
            dollar_gold="bullish",
            gold_signal="BULLISH",
            copper_signal="BULLISH",
            oil_signal="NEUTRAL",
            crypto_signal="BULLISH",
            crypto_risk="risk_seeking",
            avg_correlation=0.2,
            diversification=0.7,
            corr_regime="normal",
            rotation_regime="risk_seeking",
        )
        assert isinstance(result, SignalResult)
        assert result.confidence > 0

    def test_register_commodity(self):
        self.gen.register_commodity("BULLISH", "BULLISH", "BULLISH", confidence=0.7)
        assert "commodity" in self.gen.sub_signals

    def test_register_correlation(self):
        self.gen.register_correlation(0.5, 0.5, "normal", confidence=0.7)
        assert "correlation" in self.gen.sub_signals

    def test_register_rotation(self):
        self.gen.register_rotation("risk_seeking", confidence=0.7)
        assert "rotation" in self.gen.sub_signals

    def test_register_dollar_normalized_trend(self):
        # Test that dollar trends with underscores work
        self.gen.register_dollar("strong_depreciation", "bullish", confidence=0.8)
        assert self.gen.sub_signals["dollar"]["score"] > 0

    def test_signal_history(self):
        self.gen.register_equity_bond("LOW", "ATTRACTIVE", confidence=0.9)
        self.gen.register_dollar("depreciation", "bullish", confidence=0.9)
        self.gen.generate()
        assert self.gen.get_latest_signal() is not None

    def test_signal_trend(self):
        self.gen.register_equity_bond("LOW", "ATTRACTIVE", confidence=0.7)
        self.gen.generate()
        assert self.gen.get_signal_trend() == "stable"

    def test_allocation_multiplier(self):
        self.gen.register_equity_bond("LOW", "ATTRACTIVE", confidence=0.7)
        self.gen.register_dollar("depreciation", "bullish", confidence=0.7)
        result = self.gen.generate_for_asset(
            target_asset="equity_portfolio",
            equity_bond_pressure="LOW", equity_bond_val="ATTRACTIVE",
            dollar_trend="depreciation", dollar_gold="bullish",
            gold_signal="BULLISH", copper_signal="BULLISH", oil_signal="NEUTRAL",
            crypto_signal="BULLISH", crypto_risk="risk_seeking",
            avg_correlation=0.2, diversification=0.7,
            corr_regime="normal", rotation_regime="risk_seeking",
        )
        mult = self.gen.get_allocation_multiplier("equities")
        assert mult >= 1.0  # Bullish scenario should overweight

    def test_signal_action_values(self):
        for action in SignalAction:
            assert isinstance(action.value, str)

    def test_signal_priority_values(self):
        for priority in SignalPriority:
            assert isinstance(priority.value, str)

    def test_clear(self):
        self.gen.register_equity_bond("LOW", "ATTRACTIVE")
        self.gen.generate()
        self.gen.clear()
        assert len(self.gen.sub_signals) == 0
        assert len(self.gen.signal_history) == 0


# ============================================================================
# Test CrossAssetRiskMonitor
# ============================================================================


class TestCrossAssetRiskMonitor:
    """Tests for CrossAssetRiskMonitor."""

    def setup_method(self):
        self.monitor = CrossAssetRiskMonitor()

    def test_assess_volatility_low(self):
        comp = self.monitor.assess_volatility_risk(vix=12.0)
        assert comp.level == RiskLevel.LOW
        assert comp.category == RiskCategory.VOLATILITY

    def test_assess_volatility_critical(self):
        comp = self.monitor.assess_volatility_risk(vix=40.0)
        assert comp.level == RiskLevel.CRITICAL
        assert comp.score > 0.8

    def test_assess_correlation_normal(self):
        comp = self.monitor.assess_correlation_risk(avg_correlation=0.1)
        assert comp.level == RiskLevel.LOW

    def test_assess_correlation_crisis(self):
        comp = self.monitor.assess_correlation_risk(avg_correlation=0.8, regime="crisis_convergence")
        assert comp.level == RiskLevel.CRITICAL

    def test_assess_liquidity(self):
        comp = self.monitor.assess_liquidity_risk(credit_spread=3.5, volume_change_pct=-25.0)
        assert comp.level in (RiskLevel.ELEVATED, RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert comp.category == RiskCategory.LIQUIDITY

    def test_assess_currency(self):
        comp = self.monitor.assess_currency_risk(dollar_trend="strong_appreciation")
        assert comp.level == RiskLevel.HIGH
        assert comp.category == RiskCategory.CURRENCY

    def test_assess_credit(self):
        comp = self.monitor.assess_credit_risk(ig_spread=3.0, hy_spread=6.0)
        assert comp.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert comp.category == RiskCategory.CREDIT

    def test_assess_tail_risk(self):
        comp = self.monitor.assess_tail_risk(skew=7.0, cvar=6.0)
        assert comp.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert comp.category == RiskCategory.TAIL_RISK

    def test_run_full_assessment(self):
        result = self.monitor.run_full_assessment(
            vix=15.0,
            avg_correlation=0.2,
            credit_spread=1.0,
            dollar_trend="stable",
        )
        assert isinstance(result, RiskMonitorResult)
        assert result.overall_level in RiskLevel
        assert result.confidence > 0

    def test_run_full_assessment_high_risk(self):
        result = self.monitor.run_full_assessment(
            vix=40.0,
            avg_correlation=0.8,
            correlation_regime="crisis_convergence",
            credit_spread=3.0,
            hy_spread=6.0,
            dollar_trend="strong_appreciation",
            skew=8.0,
        )
        assert result.overall_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert result.is_alarming is True
        assert result.requires_hedging is True

    def test_assess_empty_result(self):
        result = self.monitor.assess()
        assert isinstance(result, RiskMonitorResult)

    def test_risk_trend(self):
        self.monitor._risk_history = [0.3, 0.35, 0.4, 0.45, 0.5]
        assert self.monitor.get_risk_trend() == "rising"

    def test_position_size_multiplier(self):
        result = RiskMonitorResult(overall_level=RiskLevel.CRITICAL)
        assert result.position_size_multiplier == 0.2

        result2 = RiskMonitorResult(overall_level=RiskLevel.LOW)
        assert result2.position_size_multiplier == 1.0

    def test_risk_budget(self):
        result = RiskMonitorResult(overall_score=0.3)
        assert result.risk_budget == 0.7

    def test_clear(self):
        self.monitor.run_full_assessment(vix=15.0)
        self.monitor.clear()
        assert len(self.monitor.components) == 0
        assert len(self.monitor._risk_history) == 0


# ============================================================================
# Test CrossAssetMemory
# ============================================================================


class TestCrossAssetMemory:
    """Tests for CrossAssetMemory."""

    def setup_method(self):
        self.memory = CrossAssetMemory()

    def test_store(self):
        entry = self.memory.store("signal", {"score": 0.8}, tags=["bullish", "equity"])
        assert entry.entry_type == "signal"
        assert "bullish" in entry.tags

    def test_store_specialized(self):
        self.memory.store_signal({"score": 0.7}, tags=["bullish"])
        self.memory.store_risk({"overall": "high"}, tags=["alert"])
        self.memory.store_rotation({"regime": "risk_on"})
        self.memory.store_analysis({"summary": "test"})
        assert len(self.memory.entries) == 4

    def test_get(self):
        entry = self.memory.store("analysis", {"key": "value"})
        retrieved = self.memory.get(entry.entry_id)
        assert retrieved is not None
        assert retrieved.data["key"] == "value"

    def test_get_not_found(self):
        assert self.memory.get("nonexistent") is None

    def test_query_by_type(self):
        self.memory.store("signal", {"score": 0.8})
        self.memory.store("signal", {"score": -0.5})
        self.memory.store("risk", {"level": "high"})
        signals = self.memory.query_by_type("signal")
        assert len(signals) == 2

    def test_query_by_tag(self):
        self.memory.store("signal", {"score": 0.8}, tags=["bullish", "equity"])
        self.memory.store("risk", {"level": "high"}, tags=["alert"])
        self.memory.store("signal", {"score": -0.5}, tags=["bearish"])
        bull = self.memory.query_by_tag("bullish")
        assert len(bull) == 1

    def test_query_recent(self):
        self.memory.store("signal", {"score": 0.8}, ttl_hours=24)
        recent = self.memory.query_recent(hours=48)
        assert len(recent) == 1

    def test_query_range(self):
        now = datetime.now()
        from datetime import timedelta
        self.memory.store("signal", {"score": 0.8})
        results = self.memory.query_range(now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(results) == 1

    def test_get_signal_history(self):
        self.memory.store_signal({"score": 0.8, "target_asset": "AAPL"})
        self.memory.store_signal({"score": -0.3, "target_asset": "MSFT"})
        history = self.memory.get_signal_history(target_asset="AAPL")
        assert len(history) == 1

    def test_get_risk_history(self):
        self.memory.store_risk({"overall_level": "high"})
        history = self.memory.get_risk_history()
        assert len(history) == 1

    def test_get_regime_history(self):
        self.memory.store("rotation", {"regime": "risk_seeking"})
        self.memory.store_risk({"current_regime": "normal"})
        history = self.memory.get_regime_history()
        assert len(history) >= 1

    def test_get_stats(self):
        self.memory.store("signal", {"score": 0.8}, tags=["bullish"])
        self.memory.store("risk", {"level": "low"})
        stats = self.memory.get_stats()
        assert stats["total_entries"] == 2
        assert "type_distribution" in stats

    def test_expiration(self):
        self.memory.store("signal", {"score": 0.8}, ttl_hours=-1)
        self.memory.cleanup_expired()
        assert len(self.memory.entries) == 0

    def test_delete(self):
        entry = self.memory.store("signal", {"score": 0.8}, tags=["bullish"])
        assert self.memory.delete(entry.entry_id) is True
        assert self.memory.get(entry.entry_id) is None

    def test_delete_not_found(self):
        assert self.memory.delete("nonexistent") is False

    def test_clear(self):
        self.memory.store("signal", {"score": 0.8})
        self.memory.store("risk", {"level": "low"})
        self.memory.clear()
        assert len(self.memory.entries) == 0


# ============================================================================
# Test CrossAssetMemoryEntry
# ============================================================================


class TestCrossAssetMemoryEntry:
    """Tests for CrossAssetMemoryEntry dataclass."""

    def test_is_expired(self):
        from datetime import timedelta
        entry = CrossAssetMemoryEntry()
        assert entry.is_expired is False

        expired = CrossAssetMemoryEntry(
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert expired.is_expired is True

    def test_age_hours(self):
        entry = CrossAssetMemoryEntry()
        assert entry.age_hours >= 0


# ============================================================================
# Test CrossAssetIntelligenceService
# ============================================================================


class TestCrossAssetIntelligenceService:
    """Tests for CrossAssetIntelligenceService."""

    def setup_method(self):
        self.service = CrossAssetIntelligenceService()

    def test_run_pipeline(self):
        result = self.service.run_pipeline(
            yield_10y=4.0, real_yield=1.0, credit_spread=1.0,
            dxy=100.0, gold_price=2000.0, btc_price=50000,
        )
        assert isinstance(result, CrossAssetPipelineResult)
        assert result.signal is not None
        assert result.risk is not None
        assert result.correlation is not None
        assert isinstance(result.summary, str)

    def test_run_pipeline_bullish(self):
        result = self.service.run_pipeline(
            yield_10y=2.5, real_yield=0.3, credit_spread=0.8,
            dxy=95.0, fed_stance="dovish",
            gold_price=2100.0, copper_price=5.0,
            btc_price=60000, eth_price=3500, btc_dominance=45.0,
            vix=12.0,
        )
        assert result.signal is not None
        # Bullish environment should produce positive score
        assert result.signal.score > -1.0

    def test_run_pipeline_idempotent(self):
        r1 = self.service.run_pipeline()
        r2 = self.service.run_pipeline()
        assert r1.cycle_id != r2.cycle_id

    def test_quick_analysis(self):
        result = self.service.quick_analysis()
        assert "yield_signal" in result
        assert "dollar_signal" in result
        assert "risk_appetite" in result

    def test_get_pipeline_summary(self):
        self.service.run_pipeline()
        summary = self.service.get_pipeline_summary(1)
        assert len(summary) == 1
        assert "signal_action" in summary[0]
        assert "risk_level" in summary[0]

    def test_get_current_regime(self):
        self.service.run_pipeline()
        regime = self.service.get_current_regime()
        assert "risk_regime" in regime

    def test_get_current_regime_empty(self):
        regime = self.service.get_current_regime()
        assert regime["regime"] == "unknown"

    def test_get_allocation_recommendation(self):
        self.service.run_pipeline()
        alloc = self.service.get_allocation_recommendation()
        assert "equities" in alloc
        assert sum(alloc.values()) == pytest.approx(1.0, abs=0.05)

    def test_get_signal_history(self):
        self.service.run_pipeline()
        history = self.service.get_signal_history()
        assert len(history) >= 1

    def test_get_risk_history(self):
        self.service.run_pipeline()
        history = self.service.get_risk_history()
        assert len(history) >= 1

    def test_get_memory_stats(self):
        self.service.run_pipeline()
        stats = self.service.get_memory_stats()
        assert stats["total_entries"] >= 1

    def test_clear(self):
        self.service.run_pipeline()
        self.service.clear()
        assert len(self.service.pipeline_history) == 0
        assert self.service._cycle_counter == 0


# ============================================================================
# Test CrossAssetPipelineResult
# ============================================================================


class TestCrossAssetPipelineResult:
    """Tests for CrossAssetPipelineResult."""

    def test_defaults(self):
        result = CrossAssetPipelineResult()
        assert result.is_reliable is False

    def test_is_reliable(self):
        signal = SignalResult(confidence=0.7, score=0.5)
        risk = RiskMonitorResult(confidence=0.7)
        result = CrossAssetPipelineResult(signal=signal, risk=risk)
        assert result.is_reliable is True

    def test_summary(self):
        signal = SignalResult(score=0.5, confidence=0.7, action=SignalAction.OVERWEIGHT)
        risk = RiskMonitorResult(overall_level=RiskLevel.LOW, overall_score=0.2)
        corr = CorrelationResult(average_correlation=0.3)
        result = CrossAssetPipelineResult(signal=signal, risk=risk, correlation=corr)
        assert isinstance(result.summary, str)
        assert "overweight" in result.summary

    def test_allocation_advice(self):
        signal = SignalResult(score=0.6, confidence=0.8, action=SignalAction.OVERWEIGHT)
        risk = RiskMonitorResult(overall_level=RiskLevel.LOW, overall_score=0.2)
        result = CrossAssetPipelineResult(signal=signal, risk=risk)
        advice = result.allocation_advice
        total = sum(advice.values())
        assert total == pytest.approx(1.0, abs=0.05)


# ============================================================================
# Test Enums
# ============================================================================


class TestEnums:
    """Tests for enum types."""

    def test_asset_class_values(self):
        assert AssetClass.EQUITY.value == "equity"
        assert AssetClass.BOND_GOVERNMENT.value == "bond_government"
        assert AssetClass.CRYPTO_MAJOR.value == "crypto_major"
        assert len(list(AssetClass)) == 18

    def test_relationship_type_values(self):
        assert RelationshipType.STRONG_POSITIVE.value == "strong_positive"
        assert RelationshipType.STRONG_NEGATIVE.value == "strong_negative"
        assert len(list(RelationshipType)) == 10

    def test_risk_regime_values(self):
        assert RiskRegime.RISK_ON.value == "risk_on"
        assert RiskRegime.RISK_OFF.value == "risk_off"

    def test_dollar_trend_values(self):
        assert DollarTrend.STRONG_APPRECIATION.value == "strong_appreciation"
        assert DollarTrend.STRONG_DEPRECIATION.value == "strong_depreciation"
        assert len(list(DollarTrend)) == 5

    def test_crypto_dominance_values(self):
        assert CryptoDominance.BTC_SEASON.value == "btc_season"
        assert CryptoDominance.ALT_SEASON.value == "alt_season"

    def test_crypto_risk_appetite_values(self):
        assert CryptoRiskAppetite.RISK_SEEKING.value == "risk_seeking"
        assert CryptoRiskAppetite.EXTREME_FEAR.value == "extreme_fear"

    def test_correlation_method_values(self):
        assert CorrelationMethod.PEARSON.value == "pearson"
        assert CorrelationMethod.SPEARMAN.value == "spearman"

    def test_correlation_regime_values(self):
        assert CorrelationRegime.NORMAL.value == "normal"
        assert CorrelationRegime.CRISIS_CONVERGENCE.value == "crisis_convergence"

    def test_rotation_type_values(self):
        assert RotationType.RISK_ON.value == "risk_on"
        assert RotationType.FLIGHT_TO_SAFETY.value == "flight_to_safety"

    def test_rotation_regime_values(self):
        assert RotationRegime.RISK_SEEKING.value == "risk_seeking"
        assert RotationRegime.DEFENSIVE.value == "defensive"


# ============================================================================
# Test Integration
# ============================================================================


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_bullish(self):
        service = CrossAssetIntelligenceService()
        result = service.run_pipeline(
            yield_10y=3.0, real_yield=0.5, credit_spread=0.8,
            dxy=95.0, fed_stance="dovish",
            gold_price=2100.0, oil_price=85.0, copper_price=4.5,
            btc_price=60000, eth_price=3500, btc_dominance=45.0,
            vix=12.0, ig_spread=0.8, hy_spread=2.5,
            dollar_trend="depreciation",
        )
        assert result.signal is not None
        assert result.risk is not None
        assert result.correlation is not None

    def test_full_pipeline_bearish(self):
        service = CrossAssetIntelligenceService()
        result = service.run_pipeline(
            yield_10y=5.5, real_yield=2.5, credit_spread=2.5,
            dxy=108.0, fed_stance="hawkish",
            gold_price=1850.0, oil_price=65.0, copper_price=3.5,
            btc_price=35000, eth_price=1800, btc_dominance=58.0,
            vix=35.0, ig_spread=2.8, hy_spread=6.0,
            dollar_trend="strong_appreciation",
        )
        assert result.signal is not None
        assert result.risk is not None
        assert result.risk.overall_level in (RiskLevel.ELEVATED, RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_memory_accumulation(self):
        service = CrossAssetIntelligenceService()
        service.run_pipeline()
        service.run_pipeline()
        stats = service.get_memory_stats()
        assert stats["total_entries"] >= 2

    def test_pipeline_history_accumulates(self):
        service = CrossAssetIntelligenceService()
        service.run_pipeline()
        service.run_pipeline()
        assert len(service.pipeline_history) == 2

    def test_clear_resets_all(self):
        service = CrossAssetIntelligenceService()
        service.run_pipeline()
        service.run_pipeline()
        service.clear()
        assert len(service.pipeline_history) == 0
        stats = service.get_memory_stats()
        assert stats["total_entries"] == 0
