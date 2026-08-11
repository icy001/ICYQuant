"""Macro Agent — specialized agent for macroeconomic analysis and regime detection.

Pipeline:
    Macro data update
        -> MacroAgent.analyze() (macro indicator analysis)
        -> MacroAgent.detect_regime() (identify macro regime)
        -> MacroAgent.forecast() (generate macro forecasts)
        -> publish to blackboard / message bus
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class MacroRegime(str, Enum):
    """Macroeconomic regime classifications."""
    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    STAGFLATION = "stagflation"
    RECOVERY = "recovery"
    OVERHEATING = "overheating"
    UNKNOWN = "unknown"


@dataclass
class MacroIndicator:
    """A macroeconomic indicator.

    Attributes:
        name: Indicator name.
        value: Current value.
        previous: Previous value.
        change_pct: Percentage change.
        trend: Directional trend.
    """

    name: str = ""
    value: float = 0.0
    previous: float = 0.0
    change_pct: float = 0.0
    trend: str = "stable"


@dataclass
class MacroAnalysis:
    """Result of macroeconomic analysis.

    Attributes:
        analysis_id: Unique analysis identifier.
        regime: Detected macro regime.
        indicators: Analyzed indicators.
        gdp_growth: GDP growth estimate.
        inflation: Inflation estimate.
        interest_rate: Policy rate.
        outlook: Forward-looking assessment.
        timestamp: Analysis timestamp.
    """

    analysis_id: str = field(default_factory=lambda: uuid4().hex)
    regime: MacroRegime = MacroRegime.UNKNOWN
    indicators: List[MacroIndicator] = field(default_factory=list)
    gdp_growth: float = 0.0
    inflation: float = 0.0
    interest_rate: float = 0.0
    outlook: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MacroAgent:
    """Specialized agent for macroeconomic analysis and regime detection.

    Analyzes macroeconomic indicators, detects macro regimes, generates
    forecasts, and publishes findings for strategy and risk agents.

    Supports:
        - Macro indicator analysis
        - Regime detection (expansion, contraction, stagflation, etc.)
        - GDP, inflation, interest rate tracking
        - Forward-looking outlook generation
        - Macro alert publishing

    Usage:
        agent = MacroAgent(agent_id="macro_1", message_bus=bus)
        await agent.initialize()
        analysis = await agent.analyze(macro_data)
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Macro Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._analyses: List[MacroAnalysis] = []
        logger.info("MacroAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the macro agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("MacroAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the macro agent."""
        self._analyses.clear()
        self._initialized = False
        logger.info("MacroAgent shutdown: %s", self._agent_id)

    # ── Analysis ──

    async def analyze(
        self, macro_data: Optional[Dict[str, Any]] = None,
    ) -> MacroAnalysis:
        """Perform macroeconomic analysis.

        Args:
            macro_data: Optional macro data. Uses defaults if not provided.

        Returns:
            MacroAnalysis with regime and indicators.
        """
        data = macro_data or {}

        # Build indicators
        indicators = [
            MacroIndicator(name="GDP Growth", value=data.get("gdp", 2.5), previous=2.3, change_pct=0.2, trend="improving"),
            MacroIndicator(name="CPI Inflation", value=data.get("cpi", 3.2), previous=3.5, change_pct=-0.3, trend="declining"),
            MacroIndicator(name="Unemployment", value=data.get("unemployment", 3.8), previous=3.7, change_pct=0.1, trend="stable"),
            MacroIndicator(name="PMI", value=data.get("pmi", 52.0), previous=51.5, change_pct=0.5, trend="improving"),
            MacroIndicator(name="Policy Rate", value=data.get("rate", 5.25), previous=5.50, change_pct=-0.25, trend="declining"),
        ]

        # Detect regime
        gdp = indicators[0].value
        cpi = indicators[1].value
        regime = self._detect_regime(gdp, cpi)

        # Generate outlook
        outlook = self._generate_outlook(regime, indicators)

        analysis = MacroAnalysis(
            regime=regime,
            indicators=indicators,
            gdp_growth=gdp,
            inflation=cpi,
            interest_rate=indicators[4].value,
            outlook=outlook,
        )
        self._analyses.append(analysis)

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="macro.analysis",
                sender_id=self._agent_id,
                payload={
                    "regime": regime.value,
                    "gdp_growth": gdp,
                    "inflation": cpi,
                    "outlook": outlook,
                },
            ))

        logger.info("MacroAgent analyzed: regime=%s, gdp=%.1f%%, inflation=%.1f%%",
                    regime.value, gdp, cpi)
        return analysis

    # ── Detection ──

    def _detect_regime(self, gdp_growth: float, inflation: float) -> MacroRegime:
        """Detect macroeconomic regime.

        Args:
            gdp_growth: GDP growth rate.
            inflation: Inflation rate.

        Returns:
            Detected macro regime.
        """
        if gdp_growth > 2.0 and inflation < 3.0:
            return MacroRegime.EXPANSION
        elif gdp_growth < 0 and inflation > 3.0:
            return MacroRegime.STAGFLATION
        elif gdp_growth < 0:
            return MacroRegime.CONTRACTION
        elif gdp_growth > 0 and gdp_growth <= 2.0:
            return MacroRegime.RECOVERY
        elif inflation > 4.0:
            return MacroRegime.OVERHEATING
        return MacroRegime.UNKNOWN

    def _generate_outlook(
        self, regime: MacroRegime, indicators: List[MacroIndicator],
    ) -> str:
        """Generate forward-looking assessment.

        Args:
            regime: Current macro regime.
            indicators: Analyzed indicators.

        Returns:
            Outlook string.
        """
        outlooks = {
            MacroRegime.EXPANSION: "Positive outlook: growth with contained inflation supports risk assets",
            MacroRegime.CONTRACTION: "Cautious outlook: economic contraction favors defensive positioning",
            MacroRegime.STAGFLATION: "Negative outlook: stagflation environment is challenging for most assets",
            MacroRegime.RECOVERY: "Moderately positive: recovery phase supports gradual risk-taking",
            MacroRegime.OVERHEATING: "Warning: overheating risk may lead to policy tightening",
            MacroRegime.UNKNOWN: "Uncertain outlook: monitor key indicators for regime confirmation",
        }
        return outlooks.get(regime, outlooks[MacroRegime.UNKNOWN])

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the macro agent state.

        Returns:
            Dict with analysis count.
        """
        latest_regime = self._analyses[-1].regime.value if self._analyses else "none"
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_analyses": len(self._analyses),
            "latest_regime": latest_regime,
        }
