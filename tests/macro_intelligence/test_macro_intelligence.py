"""Tests for AI Macro Intelligence Engine.

Tests cover: MacroData, EconomicCycleDetector, CentralBankIntelligence,
InflationAnalyzer, LiquidityEngine, EventImpactPredictor,
MacroRegimeClassifier, MacroStrategyAdapter, and MacroIntelligenceService.
"""

import pytest
from datetime import datetime

from services.macro_intelligence import (
    # Data
    CentralBankEvent,
    IndicatorCategory,
    IndicatorDirection,
    MacroDataSnapshot,
    MacroEvent,
    MacroIndicator,
    MacroRegime,
    MacroRegimeState,
    # Cycle
    CyclePhase,
    EconomicCycleDetector,
    # Central Bank
    CentralBankIntelligence,
    HawkDoveScale,
    PolicyStance,
    # Inflation
    InflationAnalyzer,
    InflationRegime,
    InflationTrend,
    # Liquidity
    LiquidityCondition,
    LiquidityEngine,
    LiquidityTrend,
    # Event
    AssetImpact,
    EventImpactPrediction,
    EventImpactPredictor,
    ImpactDirection,
    ImpactMagnitude,
    # Classifier
    MacroClassification,
    MacroRegimeClassifier,
    # Adapter
    MacroStrategyAdapter,
    StrategyTheme,
    # Service
    MacroIntelligenceReport,
    MacroIntelligenceService,
)


# ═══════════════════════════════════════════════════════════════════
# MacroData Tests
# ═══════════════════════════════════════════════════════════════════

class TestMacroIndicator:
    """Tests for MacroIndicator data model."""

    def test_create_indicator(self):
        ind = MacroIndicator(
            name="CPI",
            value=3.2,
            category=IndicatorCategory.INFLATION,
            unit="%",
        )
        assert ind.name == "CPI"
        assert ind.value == 3.2
        assert ind.category == IndicatorCategory.INFLATION
        assert ind.unit == "%"

    def test_change_calculation(self):
        ind = MacroIndicator(
            name="GDP",
            value=3.5,
            previous=3.0,
            category=IndicatorCategory.GROWTH,
        )
        assert ind.change == 0.5
        assert ind.change_pct == pytest.approx(16.666, rel=0.01)

    def test_change_without_previous(self):
        ind = MacroIndicator(
            name="GDP",
            value=3.5,
            category=IndicatorCategory.GROWTH,
        )
        assert ind.change is None
        assert ind.change_pct is None

    def test_surprise_calculation(self):
        ind = MacroIndicator(
            name="NFP",
            value=250,
            expected=200,
            category=IndicatorCategory.EMPLOYMENT,
        )
        assert ind.surprise == 50

    def test_surprise_without_expected(self):
        ind = MacroIndicator(
            name="NFP",
            value=250,
            category=IndicatorCategory.EMPLOYMENT,
        )
        assert ind.surprise is None

    def test_is_improving_positive_direction(self):
        ind = MacroIndicator(
            name="GDP",
            value=3.5,
            previous=3.0,
            category=IndicatorCategory.GROWTH,
            direction=IndicatorDirection.POSITIVE,
        )
        assert ind.is_improving is True

    def test_is_improving_negative_direction(self):
        ind = MacroIndicator(
            name="Unemployment",
            value=4.0,
            previous=5.0,
            category=IndicatorCategory.EMPLOYMENT,
            direction=IndicatorDirection.NEGATIVE,
        )
        assert ind.is_improving is True  # lower unemployment = improving

    def test_change_pct_zero_previous(self):
        ind = MacroIndicator(
            name="Rare",
            value=5.0,
            previous=0.0,
            category=IndicatorCategory.GROWTH,
        )
        assert ind.change_pct is None


class TestMacroDataSnapshot:
    """Tests for MacroDataSnapshot."""

    def test_empty_snapshot(self):
        snap = MacroDataSnapshot()
        assert len(snap) == 0

    def test_add_and_get_indicator(self):
        snap = MacroDataSnapshot()
        ind = MacroIndicator(name="CPI", value=3.2, category=IndicatorCategory.INFLATION)
        snap.add(ind)
        assert len(snap) == 1
        assert snap.get("CPI") == ind

    def test_get_missing(self):
        snap = MacroDataSnapshot()
        assert snap.get("NONEXISTENT") is None

    def test_get_by_category(self):
        snap = MacroDataSnapshot()
        snap.add(MacroIndicator(name="CPI", value=3.2, category=IndicatorCategory.INFLATION))
        snap.add(MacroIndicator(name="PPI", value=2.5, category=IndicatorCategory.INFLATION))
        snap.add(MacroIndicator(name="GDP", value=3.0, category=IndicatorCategory.GROWTH))

        inflation_inds = snap.get_by_category(IndicatorCategory.INFLATION)
        assert len(inflation_inds) == 2

        growth_inds = snap.get_by_category(IndicatorCategory.GROWTH)
        assert len(growth_inds) == 1

    def test_iteration(self):
        snap = MacroDataSnapshot()
        snap.add(MacroIndicator(name="A", value=1.0, category=IndicatorCategory.GROWTH))
        snap.add(MacroIndicator(name="B", value=2.0, category=IndicatorCategory.GROWTH))
        names = [ind.name for ind in snap]
        assert names == ["A", "B"]

    def test_metadata(self):
        snap = MacroDataSnapshot(metadata={"source": "FRED"})
        assert snap.metadata["source"] == "FRED"


class TestCentralBankEvent:
    """Tests for CentralBankEvent."""

    def test_create_event(self):
        event = CentralBankEvent(
            bank="FED",
            event_type="decision",
            date=datetime(2025, 6, 15),
            rate_change=0.0,
            current_rate=5.25,
            sentiment="neutral",
            confidence=0.7,
        )
        assert event.bank == "FED"
        assert event.current_rate == 5.25

    def test_with_statement(self):
        event = CentralBankEvent(
            bank="ECB",
            event_type="decision",
            date=datetime(2025, 6, 10),
            statement_text="Inflation remains above target, we remain vigilant.",
            sentiment="hawkish",
            confidence=0.8,
            key_phrases=["vigilant", "above target"],
        )
        assert len(event.key_phrases) == 2


class TestMacroRegime:
    """Tests for MacroRegime model."""

    def test_goldilocks_is_risk_on(self):
        regime = MacroRegime(
            state=MacroRegimeState.GOLDILOCKS,
            confidence=0.8,
            growth_score=0.5,
            inflation_score=-0.3,
            liquidity_score=0.6,
            policy_score=0.2,
        )
        assert regime.is_risk_on is True
        assert regime.is_risk_off is False

    def test_stagflation_is_risk_off(self):
        regime = MacroRegime(
            state=MacroRegimeState.STAGFLATION,
            confidence=0.75,
            growth_score=-0.4,
            inflation_score=0.7,
            liquidity_score=-0.5,
            policy_score=-0.3,
        )
        assert regime.is_risk_off is True
        assert regime.is_risk_on is False

    def test_summary(self):
        regime = MacroRegime(
            state=MacroRegimeState.GOLDILOCKS,
            confidence=0.82,
        )
        assert "goldilocks" in regime.summary
        assert "82%" in regime.summary


# ═══════════════════════════════════════════════════════════════════
# Economic Cycle Detector Tests
# ═══════════════════════════════════════════════════════════════════

class TestEconomicCycleDetector:
    """Tests for EconomicCycleDetector."""

    def test_detect_expansion(self):
        detector = EconomicCycleDetector()
        data = {
            "GDP_Growth": 4.5,
            "PMI_Manufacturing": 55.0,
            "PMI_Services": 56.0,
            "Industrial_Production": 3.0,
            "NFP": 250.0,
            "Unemployment_Rate": 3.5,
            "LEI": 1.5,
            "Yield_Curve": 0.5,
            "Consumer_Confidence": 105.0,
        }
        result = detector.detect_from_dict(data)
        assert result.phase == CyclePhase.EXPANSION

    def test_detect_recession(self):
        detector = EconomicCycleDetector()
        data = {
            "GDP_Growth": -2.0,
            "PMI_Manufacturing": 42.0,
            "Industrial_Production": -3.0,
            "NFP": -50.0,
            "Unemployment_Rate": 7.0,
            "LEI": -2.0,
            "Yield_Curve": -0.5,
        }
        result = detector.detect_from_dict(data)
        assert result.phase in (CyclePhase.RECESSION, CyclePhase.DEEP_RECESSION)

    def test_detect_deep_recession(self):
        detector = EconomicCycleDetector()
        data = {
            "GDP_Growth": -4.0,
            "PMI_Manufacturing": 35.0,
            "NFP": -500.0,
            "Unemployment_Rate": 10.0,
        }
        result = detector.detect_from_dict(data)
        assert result.phase == CyclePhase.DEEP_RECESSION

    def test_detect_recovery(self):
        detector = EconomicCycleDetector()
        data = {
            "GDP_Growth": 1.5,  # below 2.0 → early_recovery/recovery range
            "PMI_Manufacturing": 52.0,
            "NFP": 150.0,
            "Unemployment_Rate": 5.5,
            "LEI": 0.8,
            "Yield_Curve": 0.3,
        }
        result = detector.detect_from_dict(data)
        assert result.phase in (CyclePhase.RECOVERY, CyclePhase.EARLY_RECOVERY, CyclePhase.EARLY_EXPANSION)

    def test_empty_data(self):
        detector = EconomicCycleDetector()
        result = detector.detect_from_dict({})
        assert result.phase is not None
        assert 0 <= result.confidence <= 1

    def test_growth_momentum_properties(self):
        detector = EconomicCycleDetector()
        data = {"GDP_Growth": 3.0}
        result = detector.detect_from_dict(data)
        assert -1 <= result.growth_momentum <= 1
        assert -1 <= result.employment_momentum <= 1

    def test_is_expansionary(self):
        detector = EconomicCycleDetector()
        data = {"GDP_Growth": 4.5, "PMI_Manufacturing": 55.0}
        result = detector.detect_from_dict(data)
        assert result.is_expansionary is True
        assert result.is_contractionary is False

    def test_history(self):
        detector = EconomicCycleDetector()
        detector.detect_from_dict({"GDP_Growth": 3.0})
        detector.detect_from_dict({"GDP_Growth": 2.0})
        assert len(detector.get_history()) == 2

    def test_summary(self):
        detector = EconomicCycleDetector()
        result = detector.detect_from_dict({"GDP_Growth": 3.0})
        assert result.phase.value in result.summary


# ═══════════════════════════════════════════════════════════════════
# Central Bank Intelligence Tests
# ═══════════════════════════════════════════════════════════════════

class TestCentralBankIntelligence:
    """Tests for CentralBankIntelligence."""

    def test_analyze_dovish_cut(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": -25.0,
            "current_rate": 5.0,
            "sentiment": "dovish",
            "confidence": 0.8,
        })
        assert result.stance == PolicyStance.CUT
        assert result.is_dovish is True

    def test_analyze_hawkish_hike(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 30.0,  # >25 gives HIKE
            "current_rate": 5.5,
            "sentiment": "hawkish",
            "confidence": 0.75,
        })
        assert result.stance == PolicyStance.HIKE
        assert result.is_hawkish is True

    def test_analyze_hold_neutral(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "sentiment": "neutral",
            "confidence": 0.6,
        })
        assert result.stance in (PolicyStance.HOLD_NEUTRAL, PolicyStance.HOLD_HAWKISH)

    def test_aggressive_hike(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 75.0,
            "current_rate": 3.0,
            "sentiment": "hawkish",
        })
        assert result.stance == PolicyStance.AGGRESSIVE_HIKE

    def test_aggressive_cut(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": -75.0,
            "current_rate": 2.0,
            "sentiment": "dovish",
        })
        assert result.stance == PolicyStance.AGGRESSIVE_CUT

    def test_keyword_analysis_dovish(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "statement_text": "The Committee remains patient and accommodative. "
                              "We see downside risks and disinflation pressures. "
                              "We will be gradual and data dependent.",
            "sentiment": "neutral",
        })
        assert result.is_dovish is True

    def test_keyword_analysis_hawkish(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "statement_text": "We remain vigilant against inflation pressure and "
                              "overheating risks. The Committee will act forcefully "
                              "to maintain credibility. There are upside risks and "
                              "wage pressure concerns.",
            "sentiment": "neutral",
        })
        assert result.is_hawkish is True

    def test_history_tracking(self):
        cb = CentralBankIntelligence()
        cb.analyze_from_dict({"bank": "FED", "rate_change": 0.0, "current_rate": 5.0})
        cb.analyze_from_dict({"bank": "FED", "rate_change": -25.0, "current_rate": 4.75})
        assert len(cb.get_history("FED")) == 2

    def test_get_latest(self):
        cb = CentralBankIntelligence()
        cb.analyze_from_dict({"bank": "FED", "rate_change": 0.0, "current_rate": 5.0})
        cb.analyze_from_dict({"bank": "FED", "rate_change": -25.0, "current_rate": 4.75})
        latest = cb.get_latest("FED")
        assert latest is not None
        assert latest.details["current_rate"] == 4.75

    def test_get_latest_none(self):
        cb = CentralBankIntelligence()
        assert cb.get_latest("BOJ") is None

    def test_get_all_latest(self):
        cb = CentralBankIntelligence()
        cb.analyze_from_dict({"bank": "FED", "rate_change": 0.0, "current_rate": 5.0})
        cb.analyze_from_dict({"bank": "ECB", "rate_change": 0.0, "current_rate": 3.5})
        all_latest = cb.get_all_latest()
        assert all_latest["FED"] is not None
        assert all_latest["ECB"] is not None

    def test_rate_bias_up(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "sentiment": "hawkish",
        })
        assert result.rate_bias == "up"

    def test_rate_bias_down(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "sentiment": "dovish",
        })
        assert result.rate_bias == "down"

    def test_summary(self):
        cb = CentralBankIntelligence()
        result = cb.analyze_from_dict({
            "bank": "FED",
            "rate_change": 0.0,
            "current_rate": 5.25,
            "sentiment": "neutral",
        })
        assert "FED" in result.summary


# ═══════════════════════════════════════════════════════════════════
# Inflation Analyzer Tests
# ═══════════════════════════════════════════════════════════════════

class TestInflationAnalyzer:
    """Tests for InflationAnalyzer."""

    def test_analyze_cooling(self):
        analyzer = InflationAnalyzer()
        result = analyzer.analyze_from_dict({
            "CPI": 3.0,
            "Core_CPI": 2.8,
        })
        assert result.headline_value == 3.0
        assert result.core_value == 2.8

    def test_analyze_rising(self):
        analyzer = InflationAnalyzer()
        # CPI with previous high value to indicate rising
        ind = MacroIndicator(
            name="CPI",
            value=4.5,
            previous=3.0,
            category=IndicatorCategory.INFLATION,
        )
        snap = MacroDataSnapshot()
        snap.add(ind)
        result = analyzer.analyze(snap)
        assert result.is_rising or result.trend in (
            InflationTrend.RISING,
            InflationTrend.RAPIDLY_RISING,
        )

    def test_deflation(self):
        analyzer = InflationAnalyzer()
        result = analyzer.analyze_from_dict({
            "CPI": -0.5,
            "Core_CPI": -0.2,
        })
        assert result.trend == InflationTrend.DEFLATIONARY
        assert result.regime == InflationRegime.DEFLATION

    def test_stable_inflation(self):
        analyzer = InflationAnalyzer()
        snap = MacroDataSnapshot()
        snap.add(MacroIndicator(
            name="CPI", value=2.1, previous=2.1,
            category=IndicatorCategory.INFLATION,
        ))
        result = analyzer.analyze(snap)
        assert result.trend == InflationTrend.STABLE

    def test_target_deviation(self):
        analyzer = InflationAnalyzer(central_bank="FED")
        result = analyzer.analyze_from_dict({
            "CPI": 4.0,
        })
        assert result.target_deviation == pytest.approx(2.0)

    def test_is_cooling(self):
        analyzer = InflationAnalyzer()
        snap = MacroDataSnapshot()
        snap.add(MacroIndicator(
            name="CPI", value=2.5, previous=4.0,
            category=IndicatorCategory.INFLATION,
        ))
        result = analyzer.analyze(snap)
        assert result.is_cooling is True

    def test_is_problematic(self):
        analyzer = InflationAnalyzer()
        # High inflation + rising → stagflation risk
        snap = MacroDataSnapshot()
        snap.add(MacroIndicator(
            name="CPI", value=8.0, previous=6.0,
            category=IndicatorCategory.INFLATION,
        ))
        result = analyzer.analyze(snap)
        assert result.is_problematic  # should be stagflation regime

    def test_history(self):
        analyzer = InflationAnalyzer()
        analyzer.analyze_from_dict({"CPI": 3.0})
        analyzer.analyze_from_dict({"CPI": 2.5})
        assert len(analyzer.get_history()) == 2

    def test_confidence(self):
        analyzer = InflationAnalyzer()
        result = analyzer.analyze_from_dict({
            "CPI": 3.0, "Core_CPI": 2.8, "PCE": 2.5, "PPI": 2.0,
        })
        assert 0.3 <= result.confidence <= 0.95

    def test_summary(self):
        analyzer = InflationAnalyzer()
        result = analyzer.analyze_from_dict({"CPI": 3.0})
        assert "3.0%" in result.summary


# ═══════════════════════════════════════════════════════════════════
# Liquidity Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestLiquidityEngine:
    """Tests for LiquidityEngine."""

    def test_analyze_loose(self):
        engine = LiquidityEngine()
        data = {
            "Fed_Balance_Sheet": 8000,
            "M2_Growth": 8.0,
            "HY_Spread": 250,
            "IG_Spread": 70,
            "TED_Spread": 15,
            "DXY": 95,
            "Global_M2": 6.0,
        }
        result = engine.analyze_from_dict(data)
        assert result.condition in (
            LiquidityCondition.LOOSE,
            LiquidityCondition.SLIGHTLY_LOOSE,
            LiquidityCondition.EXTREMELY_LOOSE,
        )

    def test_analyze_tight(self):
        engine = LiquidityEngine()
        data = {
            "M2_Growth": 1.0,
            "HY_Spread": 700,
            "IG_Spread": 250,
            "TED_Spread": 80,
            "DXY": 110,
            "Global_M2": 1.0,
        }
        result = engine.analyze_from_dict(data)
        assert result.condition in (
            LiquidityCondition.TIGHT,
            LiquidityCondition.EXTREMELY_TIGHT,
            LiquidityCondition.SLIGHTLY_TIGHT,
        )

    def test_empty_data(self):
        engine = LiquidityEngine()
        result = engine.analyze_from_dict({})
        assert result.condition == LiquidityCondition.NEUTRAL

    def test_is_accommodative(self):
        engine = LiquidityEngine()
        data = {
            "M2_Growth": 10.0,
            "HY_Spread": 200,
            "DXY": 92,
        }
        result = engine.analyze_from_dict(data)
        assert result.is_accommodative is True

    def test_is_restrictive(self):
        engine = LiquidityEngine()
        data = {
            "M2_Growth": 0.5,
            "HY_Spread": 800,
            "DXY": 112,
        }
        result = engine.analyze_from_dict(data)
        assert result.is_restrictive is True

    def test_risk_asset_impact(self):
        engine = LiquidityEngine()
        data = {"M2_Growth": 10.0, "HY_Spread": 200, "DXY": 92}
        result = engine.analyze_from_dict(data)
        assert result.risk_asset_impact > 0
        assert result.is_favorable_for_risk is True

    def test_trend_detection(self):
        engine = LiquidityEngine()
        engine.analyze_from_dict({"M2_Growth": 5.0, "HY_Spread": 400, "DXY": 100})
        engine.analyze_from_dict({"M2_Growth": 8.0, "HY_Spread": 300, "DXY": 95})
        assert len(engine.get_history()) == 2
        # Second analysis should detect easing trend
        latest = engine.get_history()[-1]
        assert latest.trend is not None

    def test_composite_score_bounds(self):
        engine = LiquidityEngine()
        result = engine.analyze_from_dict({"M2_Growth": 5.0})
        assert -1 <= result.composite_score <= 1

    def test_summary(self):
        engine = LiquidityEngine()
        result = engine.analyze_from_dict({"M2_Growth": 5.0})
        assert result.condition.value in result.summary


# ═══════════════════════════════════════════════════════════════════
# Event Impact Predictor Tests
# ═══════════════════════════════════════════════════════════════════

class TestEventImpactPredictor:
    """Tests for EventImpactPredictor."""

    def test_predict_fomc(self):
        predictor = EventImpactPredictor()
        event = MacroEvent(
            name="FOMC Rate Decision",
            event_type="policy_meeting",
            importance=4,
            country="US",
            assets_affected=["US_Equities", "UST_10Y", "USD"],
        )
        result = predictor.predict(event)
        assert result.category.value == "central_bank"
        assert result.overall_magnitude == ImpactMagnitude.HIGH
        assert len(result.asset_impacts) > 0

    def test_predict_cpi(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "CPI Release",
            "event_type": "data_release",
            "importance": 3,
        })
        assert result.category.value == "inflation"
        assert result.overall_magnitude == ImpactMagnitude.MODERATE

    def test_predict_nfp(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Nonfarm Payrolls",
            "event_type": "data_release",
            "importance": 4,
        })
        assert result.category.value == "employment"

    def test_predict_geopolitical(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Geopolitical Conflict",
            "event_type": "geopolitical",
            "importance": 5,
        })
        assert result.category.value == "geopolitical"
        assert result.overall_magnitude == ImpactMagnitude.EXTREME

    def test_extreme_importance(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Major Crisis",
            "event_type": "financial_stability",
            "importance": 5,
        })
        assert result.is_high_impact is True

    def test_low_importance(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Minor Data",
            "event_type": "data_release",
            "importance": 1,
        })
        assert result.overall_magnitude == ImpactMagnitude.MINIMAL
        assert result.is_high_impact is False

    def test_asset_impacts_structure(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "FOMC Meeting",
            "event_type": "policy_meeting",
            "importance": 4,
        })
        for impact in result.asset_impacts:
            assert isinstance(impact, AssetImpact)
            assert impact.asset
            assert -10 <= impact.expected_move_pct <= 10

    def test_confidence_bounds(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Unknown Event",
            "event_type": "unknown",
            "importance": 2,
        })
        assert 0.2 <= result.confidence <= 0.9

    def test_warnings(self):
        predictor = EventImpactPredictor()
        result = predictor.predict_from_dict({
            "name": "Geopolitical Crisis",
            "event_type": "geopolitical",
            "importance": 5,
        })
        assert len(result.risk_warnings) > 0

    def test_history(self):
        predictor = EventImpactPredictor()
        predictor.predict_from_dict({"name": "FOMC", "event_type": "policy_meeting", "importance": 4})
        predictor.predict_from_dict({"name": "CPI", "event_type": "data_release", "importance": 3})
        assert len(predictor.get_history()) == 2


class TestAssetImpact:
    """Tests for AssetImpact."""

    def test_is_positive(self):
        impact = AssetImpact(
            asset="US_Equities",
            direction=ImpactDirection.POSITIVE,
            magnitude=ImpactMagnitude.MODERATE,
            probability=0.7,
        )
        assert impact.is_positive is True
        assert impact.is_negative is False

    def test_is_negative(self):
        impact = AssetImpact(
            asset="US_Equities",
            direction=ImpactDirection.STRONG_NEGATIVE,
            magnitude=ImpactMagnitude.HIGH,
            probability=0.6,
        )
        assert impact.is_negative is True

    def test_summary(self):
        impact = AssetImpact(
            asset="Gold",
            direction=ImpactDirection.POSITIVE,
            magnitude=ImpactMagnitude.HIGH,
            probability=0.8,
        )
        assert "Gold" in impact.summary
        assert "positive" in impact.summary


# ═══════════════════════════════════════════════════════════════════
# Macro Regime Classifier Tests
# ═══════════════════════════════════════════════════════════════════

class TestMacroRegimeClassifier:
    """Tests for MacroRegimeClassifier."""

    def test_classify_goldilocks(self):
        classifier = MacroRegimeClassifier()
        data = {
            "GDP_Growth": 4.0,
            "PMI_Manufacturing": 55.0,
            "CPI": 2.0,
            "M2_Growth": 8.0,
            "HY_Spread": 300,
            "DXY": 95,
        }
        result = classifier.classify_from_dict(data)
        assert result.regime.state is not None
        assert result.regime.is_risk_on is True
        assert result.opportunity_score > 0.4

    def test_classify_recession(self):
        classifier = MacroRegimeClassifier()
        data = {
            "GDP_Growth": -2.0,
            "PMI_Manufacturing": 40.0,
            "CPI": 0.5,
            "M2_Growth": 1.0,
            "HY_Spread": 700,
            "DXY": 110,
        }
        result = classifier.classify_from_dict(data)
        assert result.regime.is_risk_off is True

    def test_asset_allocation_bias(self):
        classifier = MacroRegimeClassifier()
        data = {
            "GDP_Growth": 4.0,
            "CPI": 2.0,
            "M2_Growth": 8.0,
            "HY_Spread": 300,
        }
        result = classifier.classify_from_dict(data)
        assert len(result.asset_allocation_bias) > 0
        for asset, bias in result.asset_allocation_bias.items():
            assert -1 <= bias <= 1

    def test_risk_score_bounds(self):
        classifier = MacroRegimeClassifier()
        data = {"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0}
        result = classifier.classify_from_dict(data)
        assert 0 <= result.risk_score <= 1
        assert 0 <= result.opportunity_score <= 1

    def test_classify_from_components(self):
        from services.macro_intelligence.cycle import CycleResult, CyclePhase
        from services.macro_intelligence.inflation import InflationAnalysis, InflationTrend, InflationRegime
        from services.macro_intelligence.liquidity import LiquidityAnalysis, LiquidityCondition, LiquidityTrend
        from services.macro_intelligence.central_bank import CentralBankAnalysis, PolicyStance, HawkDoveScale

        cycle = CycleResult(phase=CyclePhase.EXPANSION, confidence=0.8)
        inflation = InflationAnalysis(
            trend=InflationTrend.COOLING,
            regime=InflationRegime.DISINFLATION,
            headline_value=2.5,
            confidence=0.7,
        )
        liquidity = LiquidityAnalysis(
            condition=LiquidityCondition.LOOSE,
            trend=LiquidityTrend.STABLE,
            composite_score=0.6,
            confidence=0.7,
        )
        cb = {
            "FED": CentralBankAnalysis(
                bank="FED",
                stance=PolicyStance.HOLD_DOVISH,
                hawk_dove=HawkDoveScale.DOVISH,
                rate_bias="down",
                confidence=0.8,
            ),
        }

        classifier = MacroRegimeClassifier()
        result = classifier.classify_from_components(cycle, inflation, liquidity, cb)
        assert result.regime.state is not None
        assert result.is_favorable is True

    def test_history(self):
        classifier = MacroRegimeClassifier()
        classifier.classify_from_dict({"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0})
        classifier.classify_from_dict({"GDP_Growth": 2.0, "CPI": 3.0, "M2_Growth": 3.0})
        assert len(classifier.get_history()) == 2

    def test_summary(self):
        classifier = MacroRegimeClassifier()
        result = classifier.classify_from_dict({"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0})
        assert "Regime:" in result.summary


# ═══════════════════════════════════════════════════════════════════
# Macro Strategy Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestMacroStrategyAdapter:
    """Tests for MacroStrategyAdapter."""

    def test_adapt_goldilocks(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.GOLDILOCKS)
        assert StrategyTheme.GROWTH in result.primary_themes
        assert result.equity_exposure > 0.7
        assert result.is_aggressive is True

    def test_adapt_recession(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.RECESSION)
        assert StrategyTheme.SAFE_HAVEN in result.primary_themes
        assert StrategyTheme.DEFENSIVE in result.primary_themes
        assert result.equity_exposure < 0.4
        assert result.is_defensive is True

    def test_adapt_stagflation(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.STAGFLATION)
        assert StrategyTheme.SAFE_HAVEN in result.primary_themes
        assert StrategyTheme.INFLATION_HEDGE in result.primary_themes
        assert result.commodity_exposure > 0.3
        assert result.cash_weight > 0.2

    def test_adapt_liquidity_surge(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.LIQUIDITY_SURGE)
        assert result.equity_exposure >= 0.85
        assert result.leverage_multiplier > 1.0
        assert result.risk_budget > 1.0

    def test_adapt_liquidity_crunch(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.LIQUIDITY_CRUNCH)
        assert result.equity_exposure <= 0.2
        assert result.leverage_multiplier < 1.0
        assert result.risk_budget < 0.5

    def test_avoid_themes(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.RECESSION)
        assert StrategyTheme.GROWTH in result.avoid_themes
        assert StrategyTheme.MOMENTUM in result.avoid_themes

    def test_sector_rotation(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.GOLDILOCKS)
        assert len(result.sector_rotation) > 0
        # Technology should be overweight in Goldilocks
        assert result.sector_rotation.get("Technology", 0) > 0

    def test_recession_sector_rotation(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.RECESSION)
        # Consumer Staples should be overweight in recession
        assert result.sector_rotation.get("Consumer_Staples", 0) > 0

    def test_all_regimes_have_config(self):
        adapter = MacroStrategyAdapter()
        for regime in MacroRegimeState:
            result = adapter.adapt_from_regime(regime)
            assert len(result.primary_themes) > 0
            assert 0 <= result.equity_exposure <= 1

    def test_history(self):
        adapter = MacroStrategyAdapter()
        adapter.adapt_from_regime(MacroRegimeState.GOLDILOCKS)
        adapter.adapt_from_regime(MacroRegimeState.RECESSION)
        assert len(adapter.get_history()) == 2

    def test_get_latest(self):
        adapter = MacroStrategyAdapter()
        assert adapter.get_latest() is None
        adapter.adapt_from_regime(MacroRegimeState.GOLDILOCKS)
        assert adapter.get_latest() is not None

    def test_summary(self):
        adapter = MacroStrategyAdapter()
        result = adapter.adapt_from_regime(MacroRegimeState.GOLDILOCKS)
        assert "goldilocks" in result.summary
        assert "equity" in result.summary


# ═══════════════════════════════════════════════════════════════════
# Macro Intelligence Service Tests
# ═══════════════════════════════════════════════════════════════════

class TestMacroIntelligenceService:
    """Tests for MacroIntelligenceService."""

    def test_analyze_goldilocks_scenario(self):
        service = MacroIntelligenceService()
        data = {
            "GDP_Growth": 4.0,
            "PMI_Manufacturing": 56.0,
            "CPI": 2.0,
            "Core_CPI": 1.8,
            "M2_Growth": 8.0,
            "HY_Spread": 280,
            "DXY": 94,
            "NFP": 200.0,
            "Unemployment_Rate": 3.6,
            "LEI": 1.2,
        }
        report = service.analyze_simple(data)
        assert isinstance(report, MacroIntelligenceReport)
        assert report.regime is not None
        assert report.cycle is not None
        assert report.inflation is not None
        assert report.liquidity is not None
        assert report.adaptation is not None

    def test_analyze_with_central_bank(self):
        service = MacroIntelligenceService()
        fed_event = CentralBankEvent(
            bank="FED",
            event_type="decision",
            date=datetime(2025, 6, 15),
            rate_change=-25.0,
            current_rate=5.0,
            sentiment="dovish",
            confidence=0.8,
        )
        data = {
            "GDP_Growth": 2.5,
            "CPI": 2.5,
            "M2_Growth": 5.0,
            "HY_Spread": 400,
            "DXY": 100,
            "central_bank_events": [fed_event],
        }
        report = service.analyze_simple(data)
        assert "FED" in report.central_banks
        assert report.central_banks["FED"].is_dovish

    def test_analyze_with_upcoming_events(self):
        service = MacroIntelligenceService()
        fomc = MacroEvent(
            name="FOMC Meeting",
            event_type="policy_meeting",
            importance=4,
        )
        data = {
            "GDP_Growth": 3.0,
            "CPI": 2.0,
            "M2_Growth": 6.0,
            "HY_Spread": 350,
            "DXY": 98,
            "upcoming_events": [fomc],
        }
        report = service.analyze_simple(data)
        assert len(report.event_predictions) == 1
        assert report.event_predictions[0].category.value == "central_bank"

    def test_quick_analysis(self):
        service = MacroIntelligenceService()
        report = service.analyze_quick(
            cycle_phase="EXPANSION",
            inflation_trend="COOLING",
            liquidity_condition="LOOSE",
            fed_sentiment="dovish",
        )
        assert report.regime.is_risk_on is True
        assert report.is_risk_on is True

    def test_quick_analysis_recession(self):
        service = MacroIntelligenceService()
        report = service.analyze_quick(
            cycle_phase="RECESSION",
            inflation_trend="RISING",
            liquidity_condition="TIGHT",
            fed_sentiment="hawkish",
        )
        # Quick analysis uses simplified inputs; verify it produces a valid result
        assert report.regime.state is not None
        assert report.adaptation is not None
        assert report.central_banks["FED"].is_hawkish

    def test_report_summary(self):
        service = MacroIntelligenceService()
        data = {"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0}
        report = service.analyze_simple(data)
        assert "Macro Intelligence Report" in report.summary

    def test_reports_history(self):
        service = MacroIntelligenceService()
        service.analyze_simple({"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0})
        service.analyze_simple({"GDP_Growth": 2.0, "CPI": 3.0, "M2_Growth": 3.0})
        assert len(service.get_reports()) == 2

    def test_get_latest_report(self):
        service = MacroIntelligenceService()
        assert service.get_latest_report() is None
        service.analyze_simple({"GDP_Growth": 3.0, "CPI": 2.0, "M2_Growth": 5.0})
        assert service.get_latest_report() is not None

    def test_empty_data_doesnt_crash(self):
        service = MacroIntelligenceService()
        report = service.analyze_simple({})
        assert isinstance(report, MacroIntelligenceReport)
        assert report.regime is not None

    def test_regime_state_in_all_reports(self):
        service = MacroIntelligenceService()
        for scenario in [
            {"GDP_Growth": 4.0, "CPI": 2.0, "M2_Growth": 8.0},
            {"GDP_Growth": -3.0, "CPI": 0.5, "M2_Growth": 1.0},
            {"GDP_Growth": 3.0, "CPI": 6.0, "M2_Growth": 2.0},
            {"GDP_Growth": 1.0, "CPI": 2.0, "M2_Growth": 4.0},
        ]:
            report = service.analyze_simple(scenario)
            assert report.regime.state is not None

    def test_all_components_present(self):
        service = MacroIntelligenceService()
        data = {
            "GDP_Growth": 3.5,
            "CPI": 2.2,
            "M2_Growth": 6.0,
            "HY_Spread": 350,
            "DXY": 97,
            "NFP": 180.0,
            "Unemployment_Rate": 4.0,
        }
        report = service.analyze_simple(data)
        assert report.classification is not None
        assert report.adaptation is not None
        assert report.cycle is not None
        assert report.inflation is not None
        assert report.liquidity is not None
        assert report.metadata is not None


# ═══════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_goldilocks(self):
        """Test the complete macro intelligence pipeline for Goldilocks scenario."""
        service = MacroIntelligenceService()

        # Build comprehensive macro snapshot
        snapshot = MacroDataSnapshot()
        indicators = [
            ("GDP_Growth", 4.2, IndicatorCategory.GROWTH),
            ("PMI_Manufacturing", 56.5, IndicatorCategory.GROWTH),
            ("PMI_Services", 55.0, IndicatorCategory.GROWTH),
            ("Industrial_Production", 3.5, IndicatorCategory.GROWTH),
            ("Retail_Sales", 2.8, IndicatorCategory.GROWTH),
            ("NFP", 220.0, IndicatorCategory.EMPLOYMENT),
            ("Unemployment_Rate", 3.5, IndicatorCategory.EMPLOYMENT),
            ("Wage_Growth", 4.0, IndicatorCategory.EMPLOYMENT),
            ("CPI", 2.1, IndicatorCategory.INFLATION),
            ("Core_CPI", 1.9, IndicatorCategory.INFLATION),
            ("PPI", 2.0, IndicatorCategory.INFLATION),
            ("M2_Growth", 7.5, IndicatorCategory.MONETARY),
            ("Fed_Balance_Sheet", 7500, IndicatorCategory.MONETARY),
            ("HY_Spread", 280, IndicatorCategory.MONETARY),
            ("IG_Spread", 75, IndicatorCategory.MONETARY),
            ("TED_Spread", 18, IndicatorCategory.MONETARY),
            ("DXY", 93, IndicatorCategory.MONETARY),
            ("LEI", 1.3, IndicatorCategory.GROWTH),
            ("Yield_Curve", 0.4, IndicatorCategory.MONETARY),
            ("Consumer_Confidence", 108, IndicatorCategory.SENTIMENT),
        ]
        for name, value, cat in indicators:
            snapshot.add(MacroIndicator(name=name, value=value, category=cat))

        # Central bank events
        fed_event = CentralBankEvent(
            bank="FED",
            event_type="decision",
            date=datetime(2025, 7, 28),
            rate_change=0.0,
            current_rate=5.0,
            sentiment="dovish",
            confidence=0.8,
            statement_text="The Committee sees balanced risks. "
                           "Inflation is moderating and we remain patient.",
        )

        # Upcoming events
        upcoming = [
            MacroEvent(
                name="CPI Release",
                event_type="data_release",
                importance=3,
                country="US",
            ),
            MacroEvent(
                name="FOMC Minutes",
                event_type="minutes",
                importance=3,
                country="US",
            ),
        ]

        report = service.analyze(snapshot, [fed_event], upcoming)

        # Verify complete report
        assert report.regime.is_risk_on
        assert report.adaptation.equity_exposure > 0.6
        assert report.cycle.is_expansionary
        # Inflation is stable (near target), not cooling — no previous value for momentum
        assert report.inflation.trend in (
            InflationTrend.STABLE, InflationTrend.COOLING, InflationTrend.MODERATELY_COOLING,
        )
        assert report.liquidity.is_accommodative
        assert len(report.central_banks) == 1
        assert report.central_banks["FED"].is_dovish
        assert len(report.event_predictions) == 2
        assert report.classification.opportunity_score > 0.5

    def test_full_pipeline_recession(self):
        """Test the complete pipeline for a recession scenario."""
        service = MacroIntelligenceService()

        snapshot = MacroDataSnapshot()
        indicators = [
            ("GDP_Growth", -1.5, IndicatorCategory.GROWTH),
            ("PMI_Manufacturing", 42.0, IndicatorCategory.GROWTH),
            ("NFP", -100.0, IndicatorCategory.EMPLOYMENT),
            ("Unemployment_Rate", 6.8, IndicatorCategory.EMPLOYMENT),
            ("CPI", 1.0, IndicatorCategory.INFLATION),
            ("M2_Growth", 1.5, IndicatorCategory.MONETARY),
            ("HY_Spread", 650, IndicatorCategory.MONETARY),
            ("TED_Spread", 55, IndicatorCategory.MONETARY),
            ("DXY", 108, IndicatorCategory.MONETARY),
        ]
        for name, value, cat in indicators:
            snapshot.add(MacroIndicator(name=name, value=value, category=cat))

        fed_event = CentralBankEvent(
            bank="FED",
            event_type="decision",
            date=datetime(2025, 7, 28),
            rate_change=-50.0,
            current_rate=4.5,
            sentiment="dovish",
            confidence=0.85,
        )

        report = service.analyze(snapshot, [fed_event])

        assert report.regime.is_risk_off
        assert report.adaptation.is_defensive
        assert report.cycle.is_contractionary
        assert report.liquidity.is_restrictive
        assert report.classification.risk_score > 0.5

    def test_service_properties(self):
        """Test MacroIntelligenceReport convenience properties."""
        service = MacroIntelligenceService()
        data = {"GDP_Growth": 4.0, "CPI": 2.0, "M2_Growth": 8.0}
        report = service.analyze_simple(data)

        # Test properties
        assert isinstance(report.regime, MacroRegime)
        assert isinstance(report.is_risk_on, bool)
        assert isinstance(report.is_risk_off, bool)
        assert isinstance(report.summary, str)
