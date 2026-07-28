"""Flow Alpha Generator.

Converts capital flow intelligence into quantifiable alpha factors
for the Alpha Research Engine. Generates institutional flow factors,
smart money factors, ETF flow factors, and composite capital factors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import CapitalFlowRecord, FlowAlphaSignal, FlowSource, FlowDirection


@dataclass
class FlowAlphaResult:
    """Result of flow alpha generation.

    Attributes:
        signals: Generated alpha signals.
        signal_count: Number of signals generated.
        aggregate_score: Composite alpha score across all signals.
        metadata: Generation context and parameters.
        timestamp: Generation timestamp.
    """

    signals: list[FlowAlphaSignal] = field(default_factory=list)
    signal_count: int = 0
    aggregate_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_signals(self) -> bool:
        return len(self.signals) > 0

    @property
    def actionable_signals(self) -> list[FlowAlphaSignal]:
        return [s for s in self.signals if s.is_actionable]

    @property
    def bullish_count(self) -> int:
        return sum(1 for s in self.signals if s.direction > 0)

    @property
    def bearish_count(self) -> int:
        return sum(1 for s in self.signals if s.direction < 0)


class FlowAlphaGenerator:
    """Generates alpha signals from capital flow intelligence.

    Produces multiple flow-based factor types:
    - Institutional Flow Factor
    - Smart Money Factor
    - ETF Flow Factor
    - Options Flow Factor
    - Liquidity Factor
    - Composite Capital Flow Factor

    Attributes:
        signal_counter: Auto-incrementing signal ID counter.
        generated_signals: History of all generated signals.
    """

    def __init__(self) -> None:
        self.signal_counter: int = 0
        self.generated_signals: list[FlowAlphaSignal] = []

    # --- Generation ---

    def generate(self, flow: dict[str, Any] | float) -> dict[str, Any]:
        """Generate alpha from flow data or value.

        Args:
            flow: Either a dict of flow data or a raw flow value.

        Returns:
            Dict with alpha signal details.
        """
        if isinstance(flow, dict):
            net_flow = flow.get("net_flow", 0.0)
            strength = flow.get("strength", abs(net_flow) / 10.0 if net_flow != 0 else 0.0)
            return {"alpha": net_flow, "strength": min(1.0, strength), "source": "flow"}
        return {"alpha": flow, "strength": abs(flow) / 10.0}

    def generate_signal(
        self,
        asset: str,
        factor_name: str,
        value: float,
        direction: int,
        confidence: float,
        horizon: int = 5,
        components: dict[str, float] | None = None,
    ) -> FlowAlphaSignal:
        """Generate a single alpha signal.

        Args:
            asset: Target asset or sector.
            factor_name: Name of the factor.
            value: Signal value (z-score style).
            direction: 1=bullish, -1=bearish, 0=neutral.
            confidence: Signal confidence [0.0, 1.0].
            horizon: Expected signal horizon in days.
            components: Contributing sub-factors.

        Returns:
            FlowAlphaSignal.
        """
        self.signal_counter += 1
        signal = FlowAlphaSignal(
            signal_id=f"FLOW_{self.signal_counter:06d}",
            asset=asset,
            factor_name=factor_name,
            value=value,
            direction=direction,
            confidence=confidence,
            horizon=horizon,
            components=components or {},
        )
        self.generated_signals.append(signal)
        return signal

    def generate_from_flows(
        self,
        asset: str,
        flows: list[CapitalFlowRecord],
        institutional_confidence: float = 0.5,
        smart_money_action: str = "WAITING",
        liquidity_score: float = 50.0,
    ) -> FlowAlphaResult:
        """Generate alpha signals from capital flow data.

        Args:
            asset: Target asset.
            flows: List of capital flow records.
            institutional_confidence: Institutional detection confidence.
            smart_money_action: Smart money action signal.
            liquidity_score: Liquidity environment score.

        Returns:
            FlowAlphaResult with generated signals.
        """
        if not flows:
            return FlowAlphaResult()

        signals: list[FlowAlphaSignal] = []

        # 1. Institutional Flow Factor
        inst_signal = self._compute_institutional_factor(asset, flows, institutional_confidence)
        if inst_signal:
            signals.append(inst_signal)

        # 2. Smart Money Factor
        smart_signal = self._compute_smart_money_factor(asset, flows, smart_money_action)
        if smart_signal:
            signals.append(smart_signal)

        # 3. ETF Flow Factor
        etf_signal = self._compute_etf_factor(asset, flows)
        if etf_signal:
            signals.append(etf_signal)

        # 4. Options Flow Factor
        opt_signal = self._compute_options_factor(asset, flows)
        if opt_signal:
            signals.append(opt_signal)

        # 5. Liquidity Factor
        liq_signal = self._compute_liquidity_factor(asset, liquidity_score)
        if liq_signal:
            signals.append(liq_signal)

        # 6. Composite Factor
        if len(signals) >= 2:
            composite = self._compute_composite_factor(asset, signals)
            if composite:
                signals.append(composite)

        aggregate = self._aggregate_signals(signals)

        return FlowAlphaResult(
            signals=signals,
            signal_count=len(signals),
            aggregate_score=aggregate,
            metadata={"asset": asset, "flow_count": len(flows)},
        )

    # --- Factor Computations ---

    def _compute_institutional_factor(
        self, asset: str, flows: list[CapitalFlowRecord], confidence: float
    ) -> FlowAlphaSignal | None:
        """Compute institutional flow alpha factor."""
        inst_sources = {FlowSource.INSTITUTIONAL, FlowSource.HEDGE_FUND, FlowSource.MUTUAL_FUND}
        inst_flows = [f for f in flows if f.source in inst_sources]
        if not inst_flows:
            return None

        net = sum(f.net_flow_value for f in inst_flows)
        total = sum(abs(f.amount) for f in inst_flows)

        if total == 0:
            return None

        value = net / total
        direction = 1 if value > 0.1 else -1 if value < -0.1 else 0

        return self.generate_signal(
            asset=asset,
            factor_name="institutional_flow",
            value=value,
            direction=direction,
            confidence=confidence,
            components={"net_flow": net, "total_amount": total, "count": float(len(inst_flows))},
        )

    def _compute_smart_money_factor(
        self, asset: str, flows: list[CapitalFlowRecord], action: str
    ) -> FlowAlphaSignal | None:
        """Compute smart money alpha factor."""
        smart_sources = {FlowSource.HEDGE_FUND, FlowSource.DARK_POOL}
        smart_flows = [f for f in flows if f.source in smart_sources]
        if not smart_flows:
            # Fallback: use all significant flows
            smart_flows = [f for f in flows if f.is_significant]
        if not smart_flows:
            return None

        net = sum(f.net_flow_value for f in smart_flows)
        total = sum(abs(f.amount) for f in smart_flows)

        if total == 0:
            return None

        value = net / total
        direction = 1 if action in ("ENTRY", "ADDING") else -1 if action in ("EXIT", "REDUCING") else 0

        return self.generate_signal(
            asset=asset,
            factor_name="smart_money",
            value=value,
            direction=direction,
            confidence=0.6 if action != "WAITING" else 0.3,
            components={"net_flow": net, "action": action},
        )

    def _compute_etf_factor(
        self, asset: str, flows: list[CapitalFlowRecord]
    ) -> FlowAlphaSignal | None:
        """Compute ETF flow alpha factor."""
        etf_flows = [f for f in flows if f.source == FlowSource.ETF]
        if not etf_flows:
            return None

        net = sum(f.net_flow_value for f in etf_flows)
        total = sum(abs(f.amount) for f in etf_flows)

        if total == 0:
            return None

        value = net / total
        direction = 1 if value > 0.1 else -1 if value < -0.1 else 0

        return self.generate_signal(
            asset=asset,
            factor_name="etf_flow",
            value=value,
            direction=direction,
            confidence=0.5,
            components={"net_flow": net, "etf_count": float(len(etf_flows))},
        )

    def _compute_options_factor(
        self, asset: str, flows: list[CapitalFlowRecord]
    ) -> FlowAlphaSignal | None:
        """Compute options flow alpha factor."""
        opt_flows = [f for f in flows if f.source == FlowSource.OPTIONS]
        if not opt_flows:
            return None

        net = sum(f.net_flow_value for f in opt_flows)
        total = sum(abs(f.amount) for f in opt_flows)

        if total == 0:
            return None

        value = net / total
        direction = 1 if value > 0.1 else -1 if value < -0.1 else 0

        # Options signals are noisier
        conf = 0.4 + 0.1 * min(1.0, len(opt_flows) / 10.0)

        return self.generate_signal(
            asset=asset,
            factor_name="options_flow",
            value=value,
            direction=direction,
            confidence=conf,
            components={"net_flow": net, "trade_count": float(len(opt_flows))},
        )

    def _compute_liquidity_factor(
        self, asset: str, liquidity_score: float
    ) -> FlowAlphaSignal | None:
        """Compute liquidity environment alpha factor."""
        # Map [0,100] score to z-score [-1, 1]
        value = (liquidity_score - 50.0) / 50.0
        direction = 1 if value > 0.1 else -1 if value < -0.1 else 0

        if direction == 0:
            return None

        return self.generate_signal(
            asset=asset,
            factor_name="liquidity_environment",
            value=value,
            direction=direction,
            confidence=0.55,
            components={"liquidity_score": liquidity_score},
        )

    def _compute_composite_factor(
        self, asset: str, signals: list[FlowAlphaSignal]
    ) -> FlowAlphaSignal | None:
        """Compute composite capital flow alpha."""
        if not signals:
            return None

        total_weight = 0.0
        weighted_value = 0.0
        for s in signals:
            weight = s.confidence
            weighted_value += s.value * weight
            total_weight += weight

        if total_weight == 0:
            return None

        composite_value = weighted_value / total_weight
        direction = 1 if composite_value > 0.05 else -1 if composite_value < -0.05 else 0
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return self.generate_signal(
            asset=asset,
            factor_name="composite_capital_flow",
            value=composite_value,
            direction=direction,
            confidence=avg_confidence,
            components={s.factor_name: s.value for s in signals},
        )

    def _aggregate_signals(self, signals: list[FlowAlphaSignal]) -> float:
        """Compute aggregate score across all signals."""
        if not signals:
            return 0.0
        actionable = [s for s in signals if s.is_actionable]
        if not actionable:
            return 0.0
        return sum(s.value * s.confidence for s in actionable) / len(actionable)

    # --- Query ---

    def get_signals_by_asset(self, asset: str) -> list[FlowAlphaSignal]:
        """Get all signals for an asset."""
        return [s for s in self.generated_signals if s.asset == asset]

    def get_signals_by_factor(self, factor_name: str) -> list[FlowAlphaSignal]:
        """Get all signals for a factor type."""
        return [s for s in self.generated_signals if s.factor_name == factor_name]

    def get_latest_signals(self, limit: int = 10) -> list[FlowAlphaSignal]:
        """Get most recent signals."""
        return self.generated_signals[-limit:]

    def clear(self) -> None:
        """Reset generator state."""
        self.signal_counter = 0
        self.generated_signals.clear()
