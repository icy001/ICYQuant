"""Cross-Asset Intelligence Service.

Orchestrates all cross-asset intelligence engines into a unified
pipeline that produces comprehensive multi-asset analysis, trading
signals, risk assessments, and allocation recommendations.

Pipeline:
    1. Equity-Bond Analysis → yield/valuation signals
    2. Dollar Intelligence → USD cycle impacts
    3. Commodity Intelligence → macro condition signals
    4. Crypto Intelligence → risk appetite barometer
    5. Correlation Analysis → cross-asset relationships
    6. Rotation Detection → capital flow patterns
    7. Signal Generation → unified trading signals
    8. Risk Assessment → systemic risk evaluation
    9. Memory Storage → persistent history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .equity_bond import EquityBondAnalyzer, EquityBondResult
from .dollar import DollarIntelligenceEngine, DollarResult
from .commodity import CommodityIntelligenceEngine, CommodityResult
from .crypto import CryptoIntelligenceEngine, CryptoResult
from .correlation import CorrelationEngine, CorrelationResult
from .rotation import AssetRotationDetector, AssetRotationResult
from .signal import CrossAssetSignalGenerator, SignalResult
from .risk import CrossAssetRiskMonitor, RiskMonitorResult
from .memory import CrossAssetMemory, CrossAssetMemoryEntry
from .relationship import AssetRelationship, RelationshipGraph


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------


@dataclass
class CrossAssetPipelineResult:
    """Complete cross-asset intelligence pipeline result.

    Attributes:
        equity_bond: Equity-bond analysis result.
        dollar: Dollar intelligence result.
        commodities: Per-commodity analysis results.
        crypto: Crypto intelligence result.
        correlation: Correlation analysis result.
        rotation: Asset rotation analysis.
        signal: Generated trading signal.
        risk: Risk assessment result.
        graph: Relationship graph.
        timestamp: Pipeline execution time.
        cycle_id: Unique cycle identifier.
        execution_time_ms: Pipeline execution time in milliseconds.
    """

    equity_bond: EquityBondResult | None = None
    dollar: DollarResult | None = None
    commodities: dict[str, CommodityResult] = field(default_factory=dict)
    crypto: CryptoResult | None = None
    correlation: CorrelationResult | None = None
    rotation: AssetRotationResult | None = None
    signal: SignalResult | None = None
    risk: RiskMonitorResult | None = None
    graph: RelationshipGraph | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    cycle_id: str = ""
    execution_time_ms: float = 0.0

    @property
    def is_reliable(self) -> bool:
        confidences: list[float] = []
        if self.signal:
            confidences.append(self.signal.confidence)
        if self.risk:
            confidences.append(self.risk.confidence)
        if not confidences:
            return False
        return sum(confidences) / len(confidences) >= 0.5

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.signal:
            parts.append(f"Signal: {self.signal.action.value} "
                         f"(score={self.signal.score:+.2f}, "
                         f"conf={self.signal.confidence:.2f})")
        if self.risk:
            parts.append(f"Risk: {self.risk.overall_level.value} "
                         f"(score={self.risk.overall_score:.2f})")
        if self.correlation:
            parts.append(f"Corr: {self.correlation.average_correlation:.2f}")
        if self.rotation and self.rotation.should_rotate:
            parts.append(f"Rotation: {self.rotation.current_regime.value}")
        return " | ".join(parts) if parts else "No data"

    @property
    def allocation_advice(self) -> dict[str, float]:
        """Derive allocation advice from all sub-results."""
        advice: dict[str, float] = {
            "equities": 0.5,
            "bonds": 0.2,
            "commodities": 0.1,
            "gold": 0.05,
            "crypto": 0.05,
            "cash": 0.1,
        }

        # Adjust from signal
        if self.signal and self.signal.is_actionable:
            mult = self.signal.risk_budget_adjustment
            advice["equities"] *= mult
            # Redistribute
            total = sum(advice.values())
            if total > 0:
                advice = {k: v / total for k, v in advice.items()}

        # Adjust from risk
        if self.risk:
            if self.risk.overall_level.value in ("high", "critical"):
                advice["cash"] += 0.15
                advice["equities"] -= 0.1
                advice["gold"] += 0.05
            elif self.risk.overall_level.value == "elevated":
                advice["cash"] += 0.05
                advice["equities"] -= 0.05

        # Normalize
        total = sum(advice.values())
        if total > 0:
            advice = {k: round(v / total, 3) for k, v in advice.items()}

        return advice


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CrossAssetIntelligenceService:
    """Orchestrates the cross-asset intelligence pipeline.

    Integrates equity-bond, dollar, commodity, crypto, correlation,
    rotation, signal, and risk engines into a coherent analysis
    pipeline for institutional multi-asset decision making.

    Attributes:
        equity_bond_analyzer: Equity-bond analysis engine.
        dollar_engine: Dollar intelligence engine.
        commodity_engine: Commodity intelligence engine.
        crypto_engine: Crypto intelligence engine.
        correlation_engine: Correlation computation engine.
        rotation_detector: Asset rotation detector.
        signal_generator: Cross-asset signal generator.
        risk_monitor: Systemic risk monitor.
        memory: Persistent analysis memory.
        pipeline_history: Recent pipeline results.
    """

    def __init__(self) -> None:
        self.equity_bond_analyzer = EquityBondAnalyzer()
        self.dollar_engine = DollarIntelligenceEngine()
        self.commodity_engine = CommodityIntelligenceEngine()
        self.crypto_engine = CryptoIntelligenceEngine()
        self.correlation_engine = CorrelationEngine()
        self.rotation_detector = AssetRotationDetector()
        self.signal_generator = CrossAssetSignalGenerator()
        self.risk_monitor = CrossAssetRiskMonitor()
        self.memory = CrossAssetMemory()
        self.pipeline_history: list[CrossAssetPipelineResult] = []
        self._cycle_counter: int = 0

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def run_pipeline(self,
                     yield_10y: float = 4.0,
                     real_yield: float = 1.0,
                     credit_spread: float = 1.0,
                     dxy: float = 100.0,
                     fed_stance: str = "neutral",
                     gold_price: float = 2000.0,
                     oil_price: float = 80.0,
                     copper_price: float = 4.0,
                     btc_price: float = 50000.0,
                     eth_price: float = 3000.0,
                     btc_dominance: float = 50.0,
                     vix: float = 15.0,
                     ig_spread: float = 1.0,
                     hy_spread: float = 3.0,
                     dollar_trend: str = "stable",
                     skew: float = 0.0,
                     var_95: float = 2.0,
                     target_asset: str = "equity_portfolio",
                     tags: list[str] | None = None) -> CrossAssetPipelineResult:
        """Execute the full cross-asset intelligence pipeline.

        Args:
            yield_10y: 10-year treasury yield.
            real_yield: Real yield.
            credit_spread: IG credit spread.
            dxy: DXY index.
            fed_stance: Fed policy stance.
            gold_price: Gold price.
            oil_price: Crude oil price.
            copper_price: Copper price.
            btc_price: Bitcoin price.
            eth_price: Ethereum price.
            btc_dominance: BTC dominance percentage.
            vix: VIX index.
            ig_spread: Investment grade spread.
            hy_spread: High yield spread.
            dollar_trend: Pre-computed dollar trend.
            skew: Options skew.
            var_95: 95% VaR.
            target_asset: Target for signal generation.
            tags: Memory tags.

        Returns:
            CrossAssetPipelineResult.
        """
        import time
        t0 = time.time()

        self._cycle_counter += 1
        cycle_id = f"CYC-{datetime.now():%Y%m%d}-{self._cycle_counter:04d}"

        # Step 1: Equity-Bond Analysis
        eq_bond = self.equity_bond_analyzer.analyze_full(yield_10y, real_yield, credit_spread)

        # Step 2: Dollar Intelligence
        dollar = self.dollar_engine.analyze_full(dxy, real_yield, fed_stance)

        # Step 3: Commodity Intelligence
        gold = self.commodity_engine.analyze_gold(gold_price, dollar_trend)
        oil = self.commodity_engine.analyze_oil(oil_price)
        copper = self.commodity_engine.analyze_copper(copper_price)

        # Step 4: Crypto Intelligence
        crypto = self.crypto_engine.analyze_full(btc_price, eth_price, btc_dominance)

        # Step 5: Correlation Analysis
        self.correlation_engine.add_prices({
            "SPX": 5000 + yield_10y * 100,  # Synthetic
            "TLT": 100 - yield_10y * 5,
            "GLD": gold_price / 10,
        })
        corr = self.correlation_engine.analyze()

        # Step 6: Rotation Detection
        # Feed performance data
        self.rotation_detector.add_performance("SPX", (yield_10y < 4) * 3.0 - credit_spread)
        self.rotation_detector.add_performance("TLT", (yield_10y > 4) * 2.0)
        rotation = self.rotation_detector.analyze_full()

        # Step 7: Signal Generation
        signal = self.signal_generator.generate_for_asset(
            target_asset=target_asset,
            equity_bond_pressure=eq_bond.equity_pressure,
            equity_bond_val=eq_bond.valuation_signal,
            dollar_trend=dollar.trend.value if isinstance(dollar.trend, object) and hasattr(dollar.trend, 'value') else str(dollar.trend),
            dollar_gold=dollar.gold_signal,
            gold_signal=gold.signal,
            copper_signal=copper.signal,
            oil_signal=oil.signal,
            crypto_signal=crypto.signal,
            crypto_risk=crypto.risk_appetite.value if hasattr(crypto.risk_appetite, 'value') else str(crypto.risk_appetite),
            avg_correlation=corr.average_correlation,
            diversification=corr.diversification_score,
            corr_regime=corr.correlation_regime.value if hasattr(corr.correlation_regime, 'value') else str(corr.correlation_regime),
            rotation_regime=rotation.current_regime.value if hasattr(rotation.current_regime, 'value') else str(rotation.current_regime),
        )

        # Step 8: Risk Assessment
        risk = self.risk_monitor.run_full_assessment(
            vix=vix,
            avg_correlation=corr.average_correlation,
            correlation_regime=corr.correlation_regime.value if hasattr(corr.correlation_regime, 'value') else "normal",
            credit_spread=ig_spread,
            hy_spread=hy_spread,
            dollar_trend=dollar_trend,
            skew=skew,
            var_95=var_95,
        )

        # Step 9: Memory Storage
        self.memory.store_signal({
            "signal_id": signal.signal_id,
            "target_asset": target_asset,
            "action": signal.action.value,
            "score": signal.score,
            "confidence": signal.confidence,
            "source_signals": signal.source_signals,
            "rationale": signal.rationale,
        }, tags=tags or ["pipeline"])

        self.memory.store_risk({
            "overall_level": risk.overall_level.value,
            "overall_score": risk.overall_score,
            "regime": risk.current_regime.value if hasattr(risk.current_regime, 'value') else str(risk.current_regime),
            "max_drawdown_risk": risk.max_drawdown_risk,
            "hedge_recommendation": risk.hedge_recommendation,
        }, tags=tags or ["pipeline"])

        execution_time = (time.time() - t0) * 1000

        result = CrossAssetPipelineResult(
            equity_bond=eq_bond,
            dollar=dollar,
            commodities={"gold": gold, "oil": oil, "copper": copper},
            crypto=crypto,
            correlation=corr,
            rotation=rotation,
            signal=signal,
            risk=risk,
            cycle_id=cycle_id,
            execution_time_ms=execution_time,
        )

        self.pipeline_history.append(result)
        if len(self.pipeline_history) > 500:
            self.pipeline_history = self.pipeline_history[-500:]

        return result

    # ------------------------------------------------------------------
    # Quick Analysis
    # ------------------------------------------------------------------

    def quick_analysis(self, yield_10y: float = 4.0, dxy: float = 100.0,
                       vix: float = 15.0, btc_price: float = 50000,
                       gold_price: float = 2000.0) -> dict[str, Any]:
        """Fast cross-asset snapshot without full pipeline.

        Args:
            yield_10y: 10-year treasury yield.
            dxy: DXY index.
            vix: VIX index.
            btc_price: Bitcoin price.
            gold_price: Gold price.

        Returns:
            Dict with concise cross-asset summary.
        """
        # Minimal analysis
        yield_signal = "bearish" if yield_10y > 5.0 else ("neutral" if yield_10y > 3.5 else "bullish")
        dollar_signal = "bearish_risk" if dxy > 105 else ("bullish_risk" if dxy < 95 else "neutral")
        vix_signal = "elevated" if vix > 25 else ("normal" if vix < 20 else "moderate")

        return {
            "yield_signal": yield_signal,
            "dollar_signal": dollar_signal,
            "vix_signal": vix_signal,
            "risk_appetite": "risk_on" if vix < 20 and yield_10y < 4.5 else "cautious",
            "gold_outlook": self.dollar_engine.get_gold_outlook(dxy),
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # History & Trend
    # ------------------------------------------------------------------

    def get_pipeline_summary(self, cycles: int = 10) -> list[dict[str, Any]]:
        """Get summary of recent pipeline cycles.

        Args:
            cycles: Number of recent cycles to report.

        Returns:
            List of cycle summaries.
        """
        recent = self.pipeline_history[-cycles:]
        return [
            {
                "cycle_id": r.cycle_id,
                "timestamp": r.timestamp.isoformat(),
                "signal_action": r.signal.action.value if r.signal else "NONE",
                "signal_score": round(r.signal.score, 3) if r.signal else 0.0,
                "risk_level": r.risk.overall_level.value if r.risk else "NONE",
                "risk_score": round(r.risk.overall_score, 3) if r.risk else 0.0,
                "avg_correlation": round(r.correlation.average_correlation, 3) if r.correlation else 0.0,
            }
            for r in recent
        ]

    def get_current_regime(self) -> dict[str, Any]:
        """Get current cross-asset regime summary.

        Returns:
            Dict with regime classification.
        """
        latest = self.pipeline_history[-1] if self.pipeline_history else None
        if not latest:
            return {"regime": "unknown", "confidence": 0.0}

        return {
            "risk_regime": latest.risk.current_regime.value if latest.risk else "unknown",
            "rotation_regime": latest.rotation.current_regime.value if latest.rotation else "unknown",
            "signal_direction": "bullish" if latest.signal and latest.signal.score > 0.1 else (
                "bearish" if latest.signal and latest.signal.score < -0.1 else "neutral"
            ),
            "confidence": latest.signal.confidence if latest.signal else 0.0,
            "timestamp": latest.timestamp.isoformat(),
        }

    def get_allocation_recommendation(self) -> dict[str, float]:
        """Get current allocation recommendation."""
        latest = self.pipeline_history[-1] if self.pipeline_history else None
        if not latest:
            return {"equities": 0.5, "bonds": 0.2, "commodities": 0.1,
                    "gold": 0.05, "crypto": 0.05, "cash": 0.1}
        return latest.allocation_advice

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def get_signal_history(self, hours: int = 72) -> list[dict[str, Any]]:
        """Get signal history from memory."""
        return self.memory.get_signal_history(hours=hours)

    def get_risk_history(self, hours: int = 72) -> list[dict[str, Any]]:
        """Get risk history from memory."""
        return self.memory.get_risk_history(hours=hours)

    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return self.memory.get_stats()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.equity_bond_analyzer.clear()
        self.dollar_engine.clear()
        self.commodity_engine.clear()
        self.crypto_engine.clear()
        self.correlation_engine.clear()
        self.rotation_detector.clear()
        self.signal_generator.clear()
        self.risk_monitor.clear()
        self.memory.clear()
        self.pipeline_history.clear()
        self._cycle_counter = 0
