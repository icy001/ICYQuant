"""Tests for Market Agent - Market Observer & Analyzer."""

import pytest
from services.agents.agent_base import AgentStatus, DecisionAction
from services.agents.market_agent import (
    MarketAgent, MarketRegime, TrendDirection, VolatilityLevel, LiquidityCondition,
)


class TestMarketAgent:
    """Market Agent lifecycle and market analysis tests."""

    @pytest.fixture
    def agent(self):
        return MarketAgent(name="test_market_agent")

    # ── Lifecycle ───────────────────────────────────────────────

    def test_initialization(self, agent):
        assert agent.name == "test_market_agent"
        assert agent.agent_type == "market_agent"
        assert agent.status in (AgentStatus.INIT, AgentStatus.IDLE)

    def test_start_stop(self, agent):
        agent.start()
        assert agent.status in (AgentStatus.IDLE, AgentStatus.OBSERVING)
        agent.stop()
        assert agent.status == AgentStatus.STOPPED

    def test_tick_flow(self, agent):
        agent.start()
        result = agent.tick()
        agent.stop()

    # ── Market Data ────────────────────────────────────────────

    def test_update_market_data(self, agent):
        agent.update_market_data("NVDA", 150.0, change_pct=2.5, volume=50_000_000)
        agent.update_market_data("AAPL", 190.0, change_pct=-0.5, volume=60_000_000)
        agent.start()
        observation = agent.observe()
        assert observation is not None
        assert observation.data is not None

    def test_update_macro(self, agent):
        agent.update_macro("gdp_growth", 2.5)
        agent.update_macro("inflation", 3.2)
        agent.update_macro("fed_rate", 5.25)
        agent.update_macro("vix", 18.5)
        # Macro data stored in agent memory
        all_facts = agent.memory.get_all_facts()
        assert isinstance(all_facts, dict)

    # ── Market Regime Detection ─────────────────────────────────

    def test_regime_detection_with_data(self, agent):
        agent.update_market_data("NVDA", 150.0, change_pct=2.5, volume=50_000_000)
        agent.update_macro("vix", 15.0)
        agent.start()
        obs = agent.observe()
        assert obs is not None
        analysis = agent.analyze(obs)
        assert analysis is not None

    def test_bearish_market(self, agent):
        agent.update_market_data("SPY", 400.0, change_pct=-3.0, volume=80_000_000)
        agent.update_macro("vix", 35.0)
        agent.start()
        obs = agent.observe()
        analysis = agent.analyze(obs)
        assert analysis is not None
        assert analysis.confidence > 0

    # ── Observation & Analysis ──────────────────────────────────

    def test_observe_returns_observation(self, agent):
        agent.start()
        agent.update_market_data("NVDA", 150.0, change_pct=1.0, volume=50_000_000)
        obs = agent.observe()
        assert obs is not None
        assert obs.source == "test_market_agent"

    def test_analyze_returns_analysis(self, agent):
        agent.start()
        agent.update_market_data("NVDA", 150.0, change_pct=1.0, volume=50_000_000)
        obs = agent.observe()
        analysis = agent.analyze(obs)
        assert analysis is not None
        assert analysis.agent == "test_market_agent"
        assert analysis.confidence > 0

    def test_decide_returns_decision(self, agent):
        agent.start()
        agent.update_market_data("NVDA", 150.0, change_pct=1.0, volume=50_000_000)
        obs = agent.observe()
        analysis = agent.analyze(obs)
        decision = agent.decide(analysis)
        assert decision is not None
        assert decision.agent == "test_market_agent"

    # ── Status Report ───────────────────────────────────────────

    def test_status_report(self, agent):
        agent.start()
        report = agent.get_status_report()
        assert "agent_name" in report
        assert "status" in report
        assert report["agent_name"] == "test_market_agent"


class TestMarketEnums:
    """Test market-related enumerations."""

    def test_market_regime_values(self):
        assert MarketRegime.RISK_ON.value == "risk_on"
        assert MarketRegime.RISK_OFF.value == "risk_off"
        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGE_BOUND.value == "range_bound"
        assert MarketRegime.CRISIS.value == "crisis"
        assert MarketRegime.UNKNOWN.value == "unknown"

    def test_trend_direction_values(self):
        assert TrendDirection.BULLISH.value == "bullish"
        assert TrendDirection.BEARISH.value == "bearish"
        assert TrendDirection.NEUTRAL.value == "neutral"

    def test_volatility_level_values(self):
        assert VolatilityLevel.HIGH.value == "high"
        assert VolatilityLevel.MEDIUM.value == "medium"
        assert VolatilityLevel.LOW.value == "low"

    def test_liquidity_condition_values(self):
        assert LiquidityCondition.TIGHT.value == "tight"
        assert LiquidityCondition.NORMAL.value == "normal"
        assert LiquidityCondition.AMPLE.value == "ample"
