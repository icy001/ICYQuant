"""Tests for AI Capital Flow Intelligence Engine."""

from __future__ import annotations

import pytest
from datetime import datetime

from services.capital_flow_intelligence import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    FlowAssetClass,
    InstitutionalBehavior,
    SmartMoneyAction,
    LiquidityRegime,
    FlowEvent,
    SectorRotation,
    FlowAlphaSignal,
    CapitalFlowCollector,
    FlowCollectionResult,
    InstitutionalFlowDetector,
    InstitutionalFlowResult,
    SmartMoneyTracker,
    SmartMoneyResult,
    ETFFlowAnalyzer,
    ETFFlowResult,
    OptionsFlowAnalyzer,
    OptionsFlowResult,
    LiquidityPredictor,
    LiquidityResult,
    CapitalRotationEngine,
    RotationResult,
    FlowAlphaGenerator,
    FlowAlphaResult,
    CapitalMemory,
    CapitalMemoryEntry,
    CapitalFlowIntelligenceService,
    FlowPipelineResult,
)


# ============================================================================
# Helper
# ============================================================================


def make_flow(
    asset: str = "AAPL",
    source: FlowSource = FlowSource.INSTITUTIONAL,
    direction: FlowDirection = FlowDirection.INFLOW,
    amount: float = 1000.0,
    confidence: float = 0.8,
    asset_class: FlowAssetClass = FlowAssetClass.EQUITY,
) -> CapitalFlowRecord:
    return CapitalFlowRecord(
        asset=asset,
        source=source,
        direction=direction,
        amount=amount,
        confidence=confidence,
        asset_class=asset_class,
    )


# ============================================================================
# Test CapitalFlowRecord
# ============================================================================


class TestCapitalFlowRecord:

    def test_create_inflow(self):
        r = make_flow(direction=FlowDirection.STRONG_INFLOW, amount=5000.0)
        assert r.is_inflow is True
        assert r.is_outflow is False
        assert r.is_strong is True
        assert r.is_significant is True

    def test_create_outflow(self):
        r = make_flow(direction=FlowDirection.OUTFLOW, amount=2000.0)
        assert r.is_inflow is False
        assert r.is_outflow is True
        assert r.is_strong is False

    def test_create_neutral(self):
        r = make_flow(direction=FlowDirection.NEUTRAL, amount=0.0)
        assert r.is_inflow is False
        assert r.is_outflow is False
        assert r.is_significant is False

    def test_net_flow_value(self):
        r = make_flow(direction=FlowDirection.INFLOW, amount=100.0, confidence=0.8)
        assert r.net_flow_value == pytest.approx(80.0)

    def test_net_flow_outflow(self):
        r = make_flow(direction=FlowDirection.OUTFLOW, amount=100.0, confidence=0.5)
        assert r.net_flow_value == pytest.approx(-50.0)

    def test_confidence_clamping(self):
        r = make_flow(confidence=1.5)
        assert r.confidence == 1.0
        r2 = make_flow(confidence=-0.5)
        assert r2.confidence == 0.0

    def test_all_sources(self):
        for source in FlowSource:
            r = CapitalFlowRecord(asset="TEST", source=source)
            assert r.source == source

    def test_metadata(self):
        r = CapitalFlowRecord(
            asset="AAPL",
            metadata={"fund": "fidelity"},
            description="Large buy order",
        )
        assert r.metadata["fund"] == "fidelity"
        assert r.description == "Large buy order"


# ============================================================================
# Test FlowEvent
# ============================================================================


class TestFlowEvent:

    def test_create_event(self):
        e = FlowEvent(
            event_id="evt_001",
            event_type="institutional_buying",
            description="Heavy institutional buying",
            assets=["AAPL", "MSFT"],
            total_amount=1000000.0,
            intensity=0.9,
        )
        assert e.is_high_impact is True
        assert e.record_count == 0

    def test_low_impact(self):
        e = FlowEvent(event_id="e2", event_type="minor", description="x", intensity=0.3)
        assert e.is_high_impact is False


# ============================================================================
# Test SectorRotation
# ============================================================================


class TestSectorRotation:

    def test_significant_rotation(self):
        r = SectorRotation(
            name="tech_to_energy",
            source_sectors=["technology"],
            target_sectors=["energy"],
            strength=0.7,
            confidence=0.8,
        )
        assert r.is_significant is True
        assert r.target_count == 1

    def test_weak_rotation(self):
        r = SectorRotation(
            name="weak",
            source_sectors=["a"],
            target_sectors=["b"],
            strength=0.2,
            confidence=0.2,
        )
        assert r.is_significant is False


# ============================================================================
# Test FlowAlphaSignal
# ============================================================================


class TestFlowAlphaSignal:

    def test_actionable(self):
        s = FlowAlphaSignal(
            signal_id="s1",
            asset="AAPL",
            factor_name="institutional_flow",
            value=0.8,
            direction=1,
            confidence=0.7,
        )
        assert s.is_actionable is True
        assert s.absolute_strength == pytest.approx(0.56)

    def test_not_actionable(self):
        s = FlowAlphaSignal(
            signal_id="s2",
            asset="MSFT",
            factor_name="neutral",
            value=0.1,
            direction=0,
            confidence=0.6,
        )
        assert s.is_actionable is False


# ============================================================================
# Test CapitalFlowCollector
# ============================================================================


class TestCapitalFlowCollector:

    def test_register_and_collect(self):
        c = CapitalFlowCollector()

        def fn(**kwargs):
            return [make_flow(asset=kwargs.get("asset", "AAPL"))]

        c.register_source(FlowSource.INSTITUTIONAL, fn)
        result = c.collect(asset="AAPL", source=FlowSource.INSTITUTIONAL)
        assert result.success is True
        assert result.count == 1

    def test_collect_unregistered(self):
        c = CapitalFlowCollector()
        result = c.collect(asset="AAPL", source=FlowSource.ETF)
        assert result.success is False

    def test_collect_no_source_returns_dict(self):
        c = CapitalFlowCollector()
        result = c.collect(asset="AAPL")
        assert isinstance(result, dict)
        assert result["asset"] == "AAPL"

    def test_collect_all(self):
        c = CapitalFlowCollector()

        def fn1(**kwargs):
            return [make_flow(asset="AAPL", source=FlowSource.ETF)]

        def fn2(**kwargs):
            return [make_flow(asset="AAPL", source=FlowSource.INSTITUTIONAL)]

        c.register_source(FlowSource.ETF, fn1)
        c.register_source(FlowSource.INSTITUTIONAL, fn2)

        results = c.collect_all(asset="AAPL")
        assert len(results) == 2
        assert c.total_records == 2

    def test_filtering(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(asset="AAPL", source=FlowSource.ETF, direction=FlowDirection.INFLOW, amount=100.0),
            make_flow(asset="MSFT", source=FlowSource.INSTITUTIONAL, direction=FlowDirection.OUTFLOW, amount=200.0),
            make_flow(asset="AAPL", source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=50.0),
        ]
        assert len(c.get_by_asset("AAPL")) == 2
        assert len(c.get_by_source(FlowSource.ETF)) == 1
        assert len(c.get_inflows()) == 2
        assert len(c.get_outflows()) == 1

    def test_net_flow_by_asset(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(asset="AAPL", direction=FlowDirection.INFLOW, amount=100.0, confidence=1.0),
            make_flow(asset="AAPL", direction=FlowDirection.OUTFLOW, amount=40.0, confidence=1.0),
        ]
        assert c.net_flow_by_asset("AAPL") == 60.0

    def test_aggregate_direction(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(asset="AAPL", direction=FlowDirection.STRONG_INFLOW, amount=10.0, confidence=1.0),
        ]
        assert c.aggregate_direction(asset="AAPL") == FlowDirection.STRONG_INFLOW

    def test_by_asset_class(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(asset="AAPL", asset_class=FlowAssetClass.EQUITY),
            make_flow(asset="TLT", asset_class=FlowAssetClass.BOND),
        ]
        assert len(c.get_by_asset_class(FlowAssetClass.EQUITY)) == 1
        assert len(c.get_by_asset_class(FlowAssetClass.BOND)) == 1

    def test_significant_filter(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(amount=100.0, confidence=0.8),
            make_flow(amount=0.0, confidence=0.5),
        ]
        assert len(c.get_significant()) == 1

    def test_strong_flows(self):
        c = CapitalFlowCollector()
        c.records = [
            make_flow(direction=FlowDirection.STRONG_INFLOW),
            make_flow(direction=FlowDirection.INFLOW),
            make_flow(direction=FlowDirection.STRONG_OUTFLOW),
        ]
        assert len(c.get_strong_flows()) == 2

    def test_clear(self):
        c = CapitalFlowCollector()

        def fn(**kwargs):
            return [make_flow()]
        c.register_source(FlowSource.INSTITUTIONAL, fn)
        c.collect(asset="AAPL", source=FlowSource.INSTITUTIONAL)
        assert c.total_records == 1
        c.clear()
        assert c.total_records == 0


# ============================================================================
# Test InstitutionalFlowDetector
# ============================================================================


class TestInstitutionalFlowDetector:

    def test_detect_with_list(self):
        d = InstitutionalFlowDetector()
        flows = [make_flow(source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=100.0)]
        result = d.detect(flows)
        assert result["institutional"] is True
        assert "behavior" in result

    def test_detect_with_dict(self):
        d = InstitutionalFlowDetector()
        result = d.detect({})
        assert result["institutional"] is True

    def test_analyze_accumulation(self):
        d = InstitutionalFlowDetector()
        flows = [
            make_flow(source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=100.0)
            for _ in range(7)
        ]
        result = d.analyze(flows)
        assert result.is_institutional is True
        assert result.behavior == InstitutionalBehavior.ACCUMULATION

    def test_analyze_distribution(self):
        d = InstitutionalFlowDetector()
        flows = [
            make_flow(source=FlowSource.INSTITUTIONAL, direction=FlowDirection.OUTFLOW, amount=100.0)
            for _ in range(7)
        ]
        result = d.analyze(flows)
        assert result.behavior == InstitutionalBehavior.DISTRIBUTION

    def test_analyze_empty(self):
        d = InstitutionalFlowDetector()
        result = d.analyze([])
        assert result.is_institutional is False

    def test_analyze_asset(self):
        d = InstitutionalFlowDetector()
        flows = [
            make_flow(asset="AAPL", direction=FlowDirection.INFLOW, amount=100.0),
            make_flow(asset="MSFT", direction=FlowDirection.OUTFLOW, amount=50.0),
        ]
        result = d.analyze_asset("AAPL", flows)
        assert result.is_institutional is True

    def test_streak(self):
        d = InstitutionalFlowDetector()
        for _ in range(5):
            d.flow_history.append(make_flow(direction=FlowDirection.INFLOW, amount=100.0))
        assert d.get_streak() == 5

    def test_trend(self):
        d = InstitutionalFlowDetector()
        for _ in range(10):
            d.flow_history.append(make_flow(direction=FlowDirection.INFLOW, amount=10.0))
        assert d.get_trend() == "accumulating"

    def test_clear(self):
        d = InstitutionalFlowDetector()
        d.flow_history.append(make_flow())
        d.clear()
        assert len(d.flow_history) == 0


# ============================================================================
# Test SmartMoneyTracker
# ============================================================================


class TestSmartMoneyTracker:

    def test_track_with_list(self):
        t = SmartMoneyTracker()
        flows = [make_flow(source=FlowSource.HEDGE_FUND, direction=FlowDirection.INFLOW, amount=5000.0)]
        result = t.track(flows)
        assert result["signal"] in ("ENTRY", "ADDING", "WAITING")

    def test_track_with_dict(self):
        t = SmartMoneyTracker()
        result = t.track({})
        assert result["signal"] == "WAITING"

    def test_analyze_entry(self):
        t = SmartMoneyTracker()
        flows = [
            make_flow(source=FlowSource.HEDGE_FUND, direction=FlowDirection.INFLOW, amount=5000.0)
            for _ in range(6)
        ]
        result = t.analyze(flows)
        assert result.action in (SmartMoneyAction.ENTRY, SmartMoneyAction.ADDING)
        assert result.is_bullish is True

    def test_analyze_exit(self):
        t = SmartMoneyTracker()
        flows = [
            make_flow(source=FlowSource.HEDGE_FUND, direction=FlowDirection.OUTFLOW, amount=5000.0)
            for _ in range(6)
        ]
        result = t.analyze(flows)
        assert result.action in (SmartMoneyAction.EXIT, SmartMoneyAction.REDUCING)
        assert result.is_bearish is True

    def test_analyze_waiting(self):
        t = SmartMoneyTracker()
        flows = [make_flow(source=FlowSource.HEDGE_FUND, direction=FlowDirection.NEUTRAL, amount=0.0)]
        result = t.analyze(flows)
        assert result.action == SmartMoneyAction.WAITING
        assert result.is_active is False

    def test_entry_exit_ratio(self):
        t = SmartMoneyTracker()
        t.entry_records = [make_flow(direction=FlowDirection.INFLOW, amount=100.0) for _ in range(3)]
        t.exit_records = [make_flow(direction=FlowDirection.OUTFLOW, amount=100.0) for _ in range(1)]
        assert t.get_entry_exit_ratio() == 3.0

    def test_smart_money_trend(self):
        t = SmartMoneyTracker()
        for _ in range(10):
            t.tracking_history.append(make_flow(direction=FlowDirection.INFLOW, amount=10.0))
        assert t.get_smart_money_trend() == "entering"

    def test_clear(self):
        t = SmartMoneyTracker()
        t.tracking_history.append(make_flow())
        t.clear()
        assert len(t.tracking_history) == 0


# ============================================================================
# Test ETFFlowAnalyzer
# ============================================================================


class TestETFFlowAnalyzer:

    def test_analyze_basic(self):
        a = ETFFlowAnalyzer()
        result = a.analyze("SMH")
        assert result["etf"] == "SMH"
        assert result["sector"] == "semiconductor"

    def test_analyze_with_flows(self):
        a = ETFFlowAnalyzer()
        flows = [
            make_flow(asset="SMH", source=FlowSource.ETF, direction=FlowDirection.INFLOW, amount=1000.0),
            make_flow(asset="SMH", source=FlowSource.ETF, direction=FlowDirection.INFLOW, amount=500.0),
        ]
        result = a.analyze("SMH", flows)
        assert result["flow"] == "positive"

    def test_analyze_full(self):
        a = ETFFlowAnalyzer()
        flows = [
            make_flow(asset="SMH", source=FlowSource.ETF, direction=FlowDirection.INFLOW, amount=1000.0, confidence=1.0)
            for _ in range(7)
        ]
        result = a.analyze_full("SMH", flows)
        assert isinstance(result, ETFFlowResult)
        assert result.sector == "semiconductor"
        assert result.is_positive_flow is True

    def test_classify_etf(self):
        a = ETFFlowAnalyzer()
        assert a.classify_etf("QQQ") == "technology"
        assert a.classify_etf("XLF") == "financial"
        assert a.classify_etf("UNKNOWN") == "unknown"

    def test_custom_mapping(self):
        a = ETFFlowAnalyzer()
        a.add_etf_mapping("CUSTOM", "my_sector")
        assert a.classify_etf("CUSTOM") == "my_sector"

    def test_sector_flow_map(self):
        a = ETFFlowAnalyzer()
        etf_flows = {
            "SMH": [make_flow(asset="SMH", direction=FlowDirection.INFLOW, amount=100.0, confidence=1.0)],
            "XLF": [make_flow(asset="XLF", direction=FlowDirection.OUTFLOW, amount=50.0, confidence=1.0)],
        }
        sector_map = a.get_sector_flow_map(etf_flows)
        assert "semiconductor" in sector_map
        assert "financial" in sector_map

    def test_detect_rotation(self):
        a = ETFFlowAnalyzer()
        etf_flows = {
            "SMH": [make_flow(asset="SMH", direction=FlowDirection.STRONG_INFLOW, amount=100.0, confidence=1.0)],
            "XLE": [make_flow(asset="XLE", direction=FlowDirection.STRONG_OUTFLOW, amount=100.0, confidence=1.0)],
        }
        rotations = a.detect_rotation(etf_flows)
        assert len(rotations) >= 1

    def test_analyze_sector(self):
        a = ETFFlowAnalyzer()
        etf_flows = {
            "SMH": [make_flow(asset="SMH", direction=FlowDirection.INFLOW, amount=100.0, confidence=1.0)],
        }
        result = a.analyze_sector("semiconductor", etf_flows)
        assert result.sector == "semiconductor"

    def test_clear(self):
        a = ETFFlowAnalyzer()
        a.flow_history["test"] = [1.0, 2.0]
        a.clear()
        assert len(a.flow_history) == 0


# ============================================================================
# Test OptionsFlowAnalyzer
# ============================================================================


class TestOptionsFlowAnalyzer:

    def test_analyze_bullish(self):
        a = OptionsFlowAnalyzer()
        flows = [
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.INFLOW, amount=2000.0),
        ]
        result = a.analyze("AAPL", flows=flows)
        assert result["bias"] == "bullish"
        assert result["put_call_ratio"] < 1.0

    def test_analyze_bearish(self):
        a = OptionsFlowAnalyzer()
        flows = [
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.OUTFLOW, amount=2000.0),
        ]
        result = a.analyze("AAPL", flows=flows)
        assert result["bias"] == "bearish"

    def test_analyze_full(self):
        a = OptionsFlowAnalyzer()
        flows = [
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.INFLOW, amount=2000000.0),
        ]
        result = a.analyze_full("AAPL", flows=flows)
        assert isinstance(result, OptionsFlowResult)
        assert result.is_bullish is True
        assert result.has_large_trades is True
        assert result.unusual_activity is True

    def test_unusual_activity_detection(self):
        a = OptionsFlowAnalyzer()
        flows = [
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.STRONG_INFLOW, amount=5000000.0),
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.STRONG_INFLOW, amount=3000000.0),
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.STRONG_INFLOW, amount=2000000.0),
        ]
        unusual = a.detect_unusual_options_activity("AAPL", flows)
        assert len(unusual) == 3

    def test_pcr_trend(self):
        a = OptionsFlowAnalyzer()
        a.call_put_history["AAPL"] = [1.0, 0.9, 0.8, 0.7]
        assert a.get_pcr_trend("AAPL") == "falling"

    def test_clear(self):
        a = OptionsFlowAnalyzer()
        a.call_put_history["AAPL"] = [1.0]
        a.clear()
        assert len(a.call_put_history) == 0


# ============================================================================
# Test LiquidityPredictor
# ============================================================================


class TestLiquidityPredictor:

    def test_predict_default(self):
        p = LiquidityPredictor()
        assert p.predict() == "NEUTRAL"

    def test_predict_expanding(self):
        p = LiquidityPredictor()
        result = p.predict({"money_supply": 80, "bond_yield": 70, "dollar": 70, "credit_spread": 70, "cb_policy": 80})
        assert result in ("EXPANDING", "ABUNDANT")

    def test_analyze_full(self):
        p = LiquidityPredictor()
        data = {"money_supply": 70, "bond_yield": 65, "dollar": 60, "credit_spread": 65, "cb_policy": 70}
        result = p.analyze(data)
        assert isinstance(result, LiquidityResult)
        assert result.is_expanding is True
        assert result.is_risk_on is True
        assert result.risk_level < 0.5

    def test_analyze_crisis(self):
        p = LiquidityPredictor()
        data = {k: 10.0 for k in p.weights}
        result = p.analyze(data)
        assert result.regime == LiquidityRegime.CRISIS
        assert result.is_risk_off is True

    def test_analyze_from_components(self):
        p = LiquidityPredictor()
        result = p.analyze_from_components(money_supply=80, cb_policy=80)
        assert isinstance(result, LiquidityResult)

    def test_trend(self):
        p = LiquidityPredictor()
        p.score_history = [50, 55, 60, 65, 70, 75, 80]
        assert p.get_trend() == "rising"

    def test_risk_asset_outlook(self):
        p = LiquidityPredictor()
        p.score_history = [80]
        assert p.get_risk_asset_outlook() == "favorable"

        p.score_history = [20]
        assert p.get_risk_asset_outlook() == "unfavorable"

    def test_clear(self):
        p = LiquidityPredictor()
        p.score_history = [50, 60, 70]
        p.clear()
        assert len(p.score_history) == 0


# ============================================================================
# Test CapitalRotationEngine
# ============================================================================


class TestCapitalRotationEngine:

    def test_detect_rotation(self):
        e = CapitalRotationEngine()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.OUTFLOW, amount=100.0)],
            "energy": [make_flow(direction=FlowDirection.INFLOW, amount=100.0)],
        }
        result = e.detect(sectors)
        assert result["has_rotation"] is True

    def test_detect_no_rotation(self):
        e = CapitalRotationEngine()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.NEUTRAL, amount=0.0)],
            "energy": [make_flow(direction=FlowDirection.NEUTRAL, amount=0.0)],
        }
        result = e.detect(sectors)
        assert result["has_rotation"] is False

    def test_detect_empty(self):
        e = CapitalRotationEngine()
        result = e.detect()
        assert result["has_rotation"] is False

    def test_analyze_result(self):
        e = CapitalRotationEngine()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.STRONG_OUTFLOW, amount=100.0)],
            "energy": [make_flow(direction=FlowDirection.STRONG_INFLOW, amount=100.0)],
        }
        result = e.analyze(sectors)
        assert isinstance(result, RotationResult)
        assert result.has_rotation is True

    def test_hottest_sectors(self):
        e = CapitalRotationEngine()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.OUTFLOW, amount=100.0)],
            "energy": [make_flow(direction=FlowDirection.INFLOW, amount=100.0)],
        }
        e.analyze(sectors)
        hot = e.get_hottest_sectors(1)
        assert hot[0][0] == "energy"

    def test_coldest_sectors(self):
        e = CapitalRotationEngine()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.OUTFLOW, amount=100.0)],
            "energy": [make_flow(direction=FlowDirection.INFLOW, amount=100.0)],
        }
        e.analyze(sectors)
        cold = e.get_coldest_sectors(1)
        assert cold[0][0] == "technology"

    def test_clear(self):
        e = CapitalRotationEngine()
        e.detected_rotations = [SectorRotation(name="test", source_sectors=["a"], target_sectors=["b"])]
        e.clear()
        assert len(e.detected_rotations) == 0


# ============================================================================
# Test FlowAlphaGenerator
# ============================================================================


class TestFlowAlphaGenerator:

    def test_generate_dict(self):
        g = FlowAlphaGenerator()
        result = g.generate({"net_flow": 100.0, "strength": 0.7})
        assert result["alpha"] == 100.0

    def test_generate_float(self):
        g = FlowAlphaGenerator()
        result = g.generate(50.0)
        assert result["alpha"] == 50.0

    def test_generate_signal(self):
        g = FlowAlphaGenerator()
        s = g.generate_signal("AAPL", "inst_flow", 0.7, 1, 0.8)
        assert s.signal_id.startswith("FLOW_")
        assert s.is_actionable is True

    def test_generate_from_flows(self):
        g = FlowAlphaGenerator()
        flows = [
            make_flow(source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=1000.0),
            make_flow(source=FlowSource.HEDGE_FUND, direction=FlowDirection.INFLOW, amount=500.0),
            make_flow(source=FlowSource.ETF, direction=FlowDirection.INFLOW, amount=300.0),
            make_flow(source=FlowSource.OPTIONS, direction=FlowDirection.INFLOW, amount=200.0),
        ]
        result = g.generate_from_flows("AAPL", flows, institutional_confidence=0.8, smart_money_action="ENTRY", liquidity_score=70.0)
        assert isinstance(result, FlowAlphaResult)
        assert result.has_signals is True

    def test_generate_empty(self):
        g = FlowAlphaGenerator()
        result = g.generate_from_flows("AAPL", [])
        assert result.has_signals is False

    def test_query(self):
        g = FlowAlphaGenerator()
        g.generate_signal("AAPL", "f1", 0.5, 1, 0.7)
        g.generate_signal("MSFT", "f1", -0.3, -1, 0.6)
        g.generate_signal("AAPL", "f2", 0.2, 0, 0.5)

        assert len(g.get_signals_by_asset("AAPL")) == 2
        assert len(g.get_signals_by_factor("f1")) == 2
        assert len(g.get_latest_signals(2)) == 2

    def test_clear(self):
        g = FlowAlphaGenerator()
        g.generate_signal("AAPL", "test", 0.5, 1, 0.7)
        g.clear()
        assert len(g.generated_signals) == 0
        assert g.signal_counter == 0


# ============================================================================
# Test CapitalMemory
# ============================================================================


class TestCapitalMemory:

    def test_save_dict(self):
        m = CapitalMemory()
        m.save({"entry_id": "t1", "notes": "test"})
        assert m.size == 1

    def test_save_entry(self):
        m = CapitalMemory()
        e = CapitalMemoryEntry(entry_id="e1", flow_data={"asset": "AAPL"})
        m.save(e)
        assert m.size == 1

    def test_save_flow(self):
        m = CapitalMemory()
        eid = m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION, SmartMoneyAction.ENTRY)
        assert eid.startswith("flow_")
        assert m.size == 1

    def test_record_outcome(self):
        m = CapitalMemory()
        eid = m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        updated = m.record_outcome(eid, "market rose", True)
        assert updated is True
        assert m.history[0].has_outcome is True
        assert m.history[0].was_accurate is True

    def test_record_outcome_not_found(self):
        m = CapitalMemory()
        assert m.record_outcome("nope", "x", True) is False

    def test_get_by_behavior(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        m.save_flow("MSFT", -500.0, InstitutionalBehavior.DISTRIBUTION)
        assert len(m.get_by_behavior(InstitutionalBehavior.ACCUMULATION)) == 1

    def test_get_by_smart_money(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION, SmartMoneyAction.ENTRY)
        m.save_flow("MSFT", -500.0, InstitutionalBehavior.DISTRIBUTION, SmartMoneyAction.EXIT)
        assert len(m.get_by_smart_money(SmartMoneyAction.ENTRY)) == 1

    def test_accuracy(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        m.record_outcome(m.history[0].entry_id, "rose", True)
        assert m.get_accuracy() == 1.0

    def test_accuracy_report(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        m.record_outcome(m.history[0].entry_id, "rose", True)
        report = m.get_accuracy_report()
        assert report["total_entries"] == 1
        assert report["overall_accuracy"] == 1.0

    def test_most_reliable_behavior(self):
        m = CapitalMemory()
        for _ in range(5):
            m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
            m.record_outcome(m.history[-1].entry_id, "rose", True)
        assert m.get_most_reliable_behavior() == InstitutionalBehavior.ACCUMULATION

    def test_smart_money_win_rate(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION, SmartMoneyAction.ENTRY)
        m.record_outcome(m.history[0].entry_id, "rose", True)
        rates = m.get_smart_money_win_rate()
        assert rates[SmartMoneyAction.ENTRY.value] == 1.0

    def test_get_recent(self):
        m = CapitalMemory()
        for _ in range(15):
            m.save_flow("AAPL", 100.0, InstitutionalBehavior.HOLDING)
        assert len(m.get_recent(10)) == 10

    def test_find(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        m.save_flow("AAPL", -500.0, InstitutionalBehavior.DISTRIBUTION)
        assert m.size == 2

    def test_clear(self):
        m = CapitalMemory()
        m.save_flow("AAPL", 1000.0, InstitutionalBehavior.ACCUMULATION)
        m.clear()
        assert m.size == 0


# ============================================================================
# Test CapitalFlowIntelligenceService
# ============================================================================


class TestCapitalFlowIntelligenceService:

    def setup_method(self):
        self.service = CapitalFlowIntelligenceService()

    def test_analyze(self):
        result = self.service.analyze({})
        assert result["institutional"] is True

    def test_run_pipeline(self):
        flows = [
            make_flow(asset="AAPL", source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=1000.0),
            make_flow(asset="AAPL", source=FlowSource.HEDGE_FUND, direction=FlowDirection.INFLOW, amount=500.0),
        ]
        result = self.service.run_pipeline(asset="AAPL", flows=flows)
        assert isinstance(result, FlowPipelineResult)
        assert result.institutional is not None
        assert result.smart_money is not None

    def test_run_pipeline_with_liquidity(self):
        result = self.service.run_pipeline(
            asset="AAPL",
            liquidity_data={"money_supply": 80, "cb_policy": 70},
        )
        assert result.liquidity is not None
        assert result.liquidity.is_risk_on is True

    def test_run_pipeline_with_rotation(self):
        sectors = {
            "technology": [make_flow(direction=FlowDirection.OUTFLOW, amount=100.0)],
            "energy": [make_flow(direction=FlowDirection.INFLOW, amount=100.0)],
        }
        result = self.service.run_pipeline(asset="AAPL", sector_data=sectors)
        assert result.rotation is not None
        assert result.rotation.has_rotation is True

    def test_run_pipeline_empty(self):
        result = self.service.run_pipeline(asset="AAPL")
        assert isinstance(result, FlowPipelineResult)

    def test_get_flow_summary(self):
        def fn(**kwargs):
            return [make_flow(asset="AAPL", direction=FlowDirection.INFLOW, amount=1000.0)]
        self.service.collector.register_source(FlowSource.INSTITUTIONAL, fn)
        self.service.collector.collect(asset="AAPL", source=FlowSource.INSTITUTIONAL)

        summary = self.service.get_flow_summary("AAPL")
        assert summary["asset"] == "AAPL"
        assert summary["record_count"] == 1

    def test_get_flow_summary_unknown(self):
        summary = self.service.get_flow_summary("UNKNOWN")
        assert summary["flow_direction"] == "unknown"

    def test_get_market_liquidity(self):
        liq = self.service.get_market_liquidity()
        assert "regime" in liq
        assert "score" in liq

    def test_get_institutional_snapshot(self):
        snapshot = self.service.get_institutional_snapshot("AAPL")
        assert snapshot["asset"] == "AAPL"

    def test_get_memory_report(self):
        report = self.service.get_memory_report()
        assert "total_entries" in report

    def test_dependency_injection(self):
        custom_d = InstitutionalFlowDetector()
        svc = CapitalFlowIntelligenceService(detector=custom_d)
        assert svc.detector is custom_d

    def test_clear(self):
        self.service.collector.records = [make_flow()]
        self.service.clear()
        assert self.service.collector.total_records == 0
        assert self.service.memory.size == 0


# ============================================================================
# Test Integration
# ============================================================================


class TestIntegration:

    def test_full_pipeline_institutional_accumulation(self):
        svc = CapitalFlowIntelligenceService()
        flows = [
            make_flow(asset="AAPL", source=FlowSource.INSTITUTIONAL, direction=FlowDirection.INFLOW, amount=10000.0)
            for _ in range(7)
        ]
        result = svc.run_pipeline(
            asset="AAPL",
            flows=flows,
            liquidity_data={"money_supply": 70, "cb_policy": 70},
        )
        assert result.institutional is not None
        assert result.institutional.behavior == InstitutionalBehavior.ACCUMULATION
        assert result.alpha is not None
        assert svc.memory.size >= 1

    def test_full_pipeline_bearish(self):
        svc = CapitalFlowIntelligenceService()
        flows = [
            make_flow(asset="MSFT", source=FlowSource.HEDGE_FUND, direction=FlowDirection.OUTFLOW, amount=10000.0)
            for _ in range(7)
        ]
        result = svc.run_pipeline(
            asset="MSFT",
            flows=flows,
            liquidity_data={"money_supply": 20, "bond_yield": 20},
        )
        assert result.institutional.behavior == InstitutionalBehavior.DISTRIBUTION
        assert result.liquidity.is_risk_off is True

    def test_rotation_in_pipeline(self):
        svc = CapitalFlowIntelligenceService()
        sectors = {
            "technology": [make_flow(direction=FlowDirection.STRONG_OUTFLOW, amount=100.0)],
            "healthcare": [make_flow(direction=FlowDirection.STRONG_INFLOW, amount=100.0)],
        }
        result = svc.run_pipeline(asset="SPY", sector_data=sectors)
        assert result.rotation is not None
        assert result.rotation.has_rotation is True

    def test_memory_accumulation(self):
        svc = CapitalFlowIntelligenceService()
        svc.run_pipeline(asset="AAPL", flows=[make_flow()])
        svc.run_pipeline(asset="MSFT", flows=[make_flow(direction=FlowDirection.OUTFLOW)])
        assert svc.memory.size >= 2


# ============================================================================
# Test FlowPipelineResult
# ============================================================================


class TestFlowPipelineResult:

    def test_defaults(self):
        r = FlowPipelineResult()
        assert r.overall_signal == "neutral"
        assert r.has_alpha is False
        assert r.risk_level == "normal"

    def test_with_results(self):
        inst = InstitutionalFlowResult(is_institutional=True, behavior=InstitutionalBehavior.ACCUMULATION)
        sm = SmartMoneyResult(action=SmartMoneyAction.ENTRY)
        liq = LiquidityResult(score=80, regime=LiquidityRegime.EXPANDING)
        r = FlowPipelineResult(institutional=inst, smart_money=sm, liquidity=liq)
        assert "accumulation" in r.overall_signal
        assert "entry" in r.overall_signal
        assert r.risk_level == "low"


# ============================================================================
# Test Enums
# ============================================================================


class TestEnums:

    def test_flow_source_values(self):
        assert FlowSource.ETF.value == "etf"
        assert FlowSource.DARK_POOL.value == "dark_pool"

    def test_flow_direction_values(self):
        assert FlowDirection.STRONG_INFLOW.value == "strong_inflow"
        assert FlowDirection.STRONG_OUTFLOW.value == "strong_outflow"

    def test_institutional_behavior_values(self):
        assert InstitutionalBehavior.ACCUMULATION.value == "accumulation"
        assert InstitutionalBehavior.DISTRIBUTION.value == "distribution"

    def test_smart_money_action_values(self):
        assert SmartMoneyAction.ENTRY.value == "entry"
        assert SmartMoneyAction.EXIT.value == "exit"

    def test_liquidity_regime_values(self):
        assert LiquidityRegime.ABUNDANT.value == "abundant"
        assert LiquidityRegime.CRISIS.value == "crisis"
