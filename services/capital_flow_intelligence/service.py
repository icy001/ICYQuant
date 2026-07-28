"""Capital Flow Intelligence Service.

Orchestrates the full AI Capital Flow Intelligence pipeline:
Data Collection → Institutional Detection → Smart Money Tracking →
ETF Analysis → Options Analysis → Liquidity Prediction →
Rotation Detection → Alpha Generation → Memory Storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .collector import CapitalFlowCollector, FlowCollectionResult
from .institutional import InstitutionalFlowDetector, InstitutionalFlowResult
from .smart_money import SmartMoneyTracker, SmartMoneyResult
from .etf_flow import ETFFlowAnalyzer, ETFFlowResult
from .options_flow import OptionsFlowAnalyzer, OptionsFlowResult
from .liquidity import LiquidityPredictor, LiquidityResult
from .rotation import CapitalRotationEngine, RotationResult
from .alpha import FlowAlphaGenerator, FlowAlphaResult
from .memory import CapitalMemory, CapitalMemoryEntry
from .record import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    FlowAssetClass,
    InstitutionalBehavior,
    SmartMoneyAction,
    LiquidityRegime,
)


@dataclass
class FlowPipelineResult:
    """Complete result of the capital flow intelligence pipeline.

    Attributes:
        institutional: Institutional flow detection result.
        smart_money: Smart money tracking result.
        etf_flow: ETF flow analysis result.
        options_flow: Options flow analysis result.
        liquidity: Liquidity prediction result.
        rotation: Capital rotation detection result.
        alpha: Flow alpha signals.
        summary: Pipeline execution summary.
        timestamp: Execution timestamp.
        duration_ms: Pipeline duration in ms.
    """

    institutional: InstitutionalFlowResult | None = None
    smart_money: SmartMoneyResult | None = None
    etf_flow: ETFFlowResult | None = None
    options_flow: OptionsFlowResult | None = None
    liquidity: LiquidityResult | None = None
    rotation: RotationResult | None = None
    alpha: FlowAlphaResult | None = None
    summary: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

    @property
    def overall_signal(self) -> str:
        signals: list[str] = []
        if self.institutional and self.institutional.is_institutional:
            signals.append(self.institutional.behavior.value)
        if self.smart_money and self.smart_money.is_active:
            signals.append(self.smart_money.action.value)
        if self.liquidity:
            signals.append(self.liquidity.regime.value)
        return " | ".join(signals) if signals else "neutral"

    @property
    def has_alpha(self) -> bool:
        return self.alpha is not None and self.alpha.has_signals

    @property
    def risk_level(self) -> str:
        if self.liquidity:
            if self.liquidity.is_risk_on:
                return "low"
            elif self.liquidity.is_risk_off:
                return "high"
        return "normal"


class CapitalFlowIntelligenceService:
    """Orchestrates the full Capital Flow Intelligence pipeline.

    Coordinates all sub-engines to provide a unified interface for:
    - Capital flow data collection
    - Institutional flow detection
    - Smart money tracking
    - ETF flow analysis
    - Options flow intelligence
    - Liquidity environment prediction
    - Capital rotation detection
    - Flow alpha factor generation

    Attributes:
        detector: Institutional flow detector.
        collector: Flow data collector.
        smart_money: Smart money tracker.
        etf_analyzer: ETF flow analyzer.
        options_analyzer: Options flow analyzer.
        liquidity: Liquidity predictor.
        rotation: Capital rotation engine.
        alpha: Flow alpha generator.
        memory: Capital flow memory.
    """

    def __init__(
        self,
        detector: InstitutionalFlowDetector | None = None,
        collector: CapitalFlowCollector | None = None,
        smart_money: SmartMoneyTracker | None = None,
        etf_analyzer: ETFFlowAnalyzer | None = None,
        options_analyzer: OptionsFlowAnalyzer | None = None,
        liquidity: LiquidityPredictor | None = None,
        rotation: CapitalRotationEngine | None = None,
        alpha: FlowAlphaGenerator | None = None,
        memory: CapitalMemory | None = None,
    ) -> None:
        self.detector = detector or InstitutionalFlowDetector()
        self.collector = collector or CapitalFlowCollector()
        self.smart_money = smart_money or SmartMoneyTracker()
        self.etf_analyzer = etf_analyzer or ETFFlowAnalyzer()
        self.options_analyzer = options_analyzer or OptionsFlowAnalyzer()
        self.liquidity = liquidity or LiquidityPredictor()
        self.rotation = rotation or CapitalRotationEngine()
        self.alpha = alpha or FlowAlphaGenerator()
        self.memory = memory or CapitalMemory()

    # --- Basic Analysis ---

    def analyze(self, flow: dict[str, Any]) -> dict[str, Any]:
        """Analyze flow data for institutional activity.

        Args:
            flow: Dict of flow data.

        Returns:
            Dict with detection result.
        """
        return self.detector.detect(flow)

    # --- Pipeline ---

    def run_pipeline(
        self,
        asset: str,
        flows: list[CapitalFlowRecord] | None = None,
        liquidity_data: dict[str, float] | None = None,
        sector_data: dict[str, list[CapitalFlowRecord]] | None = None,
    ) -> FlowPipelineResult:
        """Run the full capital flow intelligence pipeline.

        Args:
            asset: Asset identifier.
            flows: Capital flow records for the asset.
            liquidity_data: Liquidity component data.
            sector_data: Sector-level flow data for rotation detection.

        Returns:
            FlowPipelineResult with all analysis outputs.
        """
        start = datetime.now()
        all_flows = list(flows) if flows else []

        # Step 1: Institutional Flow Detection
        inst_result = self.detector.analyze(all_flows)

        # Step 2: Smart Money Tracking
        smart_result = self.smart_money.analyze(all_flows)

        # Step 3: ETF Flow Analysis
        etf_result = self.etf_analyzer.analyze_full(asset, all_flows) if all_flows else None

        # Step 4: Options Flow Analysis
        opt_result = self.options_analyzer.analyze_full(asset, flows=all_flows) if all_flows else None

        # Step 5: Liquidity Prediction
        liq_result = self.liquidity.analyze(liquidity_data or {})

        # Step 6: Capital Rotation Detection
        rot_result = self.rotation.analyze(sector_data) if sector_data else None

        # Step 7: Alpha Generation
        alpha_result = self.alpha.generate_from_flows(
            asset=asset,
            flows=all_flows,
            institutional_confidence=inst_result.confidence,
            smart_money_action=smart_result.action.value,
            liquidity_score=liq_result.score,
        )

        # Step 8: Memory
        if all_flows:
            net = sum(f.net_flow_value for f in all_flows)
            self.memory.save_flow(
                asset=asset,
                net_flow=net,
                behavior=inst_result.behavior,
                smart_money=smart_result.action,
            )

        duration = (datetime.now() - start).total_seconds() * 1000

        # Summary
        summary_parts = []
        if inst_result.is_institutional:
            summary_parts.append(f"Inst: {inst_result.behavior.value}")
        if smart_result.is_active:
            summary_parts.append(f"Smart: {smart_result.action.value}")
        if liq_result.regime != LiquidityRegime.NEUTRAL:
            summary_parts.append(f"Liq: {liq_result.regime.value}")
        if rot_result and rot_result.has_rotation:
            summary_parts.append("Rotation detected")

        return FlowPipelineResult(
            institutional=inst_result,
            smart_money=smart_result,
            etf_flow=etf_result,
            options_flow=opt_result,
            liquidity=liq_result,
            rotation=rot_result,
            alpha=alpha_result,
            summary=" | ".join(summary_parts) if summary_parts else "Analysis complete.",
            duration_ms=duration,
        )

    # --- Convenience Methods ---

    def get_flow_summary(self, asset: str) -> dict[str, Any]:
        """Get capital flow summary for an asset.

        Args:
            asset: Asset identifier.

        Returns:
            Dict with flow summary.
        """
        records = self.collector.get_by_asset(asset)
        if not records:
            return {"asset": asset, "flow_direction": "unknown"}

        net = self.collector.net_flow_by_asset(asset)
        direction = self.collector.aggregate_direction(asset=asset)

        return {
            "asset": asset,
            "net_flow": net,
            "direction": direction.value,
            "record_count": len(records),
            "inflow_count": sum(1 for r in records if r.is_inflow),
            "outflow_count": sum(1 for r in records if r.is_outflow),
        }

    def get_market_liquidity(self) -> dict[str, Any]:
        """Get overall market liquidity assessment.

        Returns:
            Dict with liquidity metrics.
        """
        liq = self.liquidity.analyze({})
        return {
            "regime": liq.regime.value,
            "score": liq.score,
            "trend": liq.trend,
            "risk_level": liq.risk_level,
            "risk_asset_outlook": self.liquidity.get_risk_asset_outlook(),
            "description": liq.description,
        }

    def get_institutional_snapshot(self, asset: str) -> dict[str, Any]:
        """Get institutional activity snapshot for an asset.

        Args:
            asset: Asset identifier.

        Returns:
            Dict with institutional snapshot.
        """
        records = self.collector.get_by_asset(asset)
        inst_records = [r for r in records if r.source == FlowSource.INSTITUTIONAL]
        result = self.detector.analyze(inst_records) if inst_records else self.detector.analyze([])

        return {
            "asset": asset,
            "institutional_activity": result.is_institutional,
            "behavior": result.behavior.value,
            "confidence": result.confidence,
            "net_flow": result.net_flow,
            "streak": result.flow_streak,
            "description": result.description,
        }

    def get_memory_report(self) -> dict[str, Any]:
        """Get report from capital flow memory.

        Returns:
            Dict with memory analysis.
        """
        return {
            "total_entries": self.memory.size,
            "accuracy_report": self.memory.get_accuracy_report(),
            "smart_money_win_rate": self.memory.get_smart_money_win_rate(),
            "most_reliable_behavior": (
                self.memory.get_most_reliable_behavior().value
                if self.memory.get_most_reliable_behavior()
                else None
            ),
        }

    def clear(self) -> None:
        """Reset all sub-engine state."""
        self.collector.clear()
        self.detector.clear()
        self.smart_money.clear()
        self.etf_analyzer.clear()
        self.options_analyzer.clear()
        self.liquidity.clear()
        self.rotation.clear()
        self.alpha.clear()
        self.memory.clear()
