"""Copilot Engine – core orchestration of AI Trading Copilot capabilities."""

from typing import Any, Dict, List, Optional

from .market_analysis import MarketAnalyst, MarketAnalysis
from .position import PositionAssistant, PositionAnalysis
from .risk_alert import RiskMonitor, RiskAlert
from .trade_plan import TradePlanner, TradePlan
from .review import TradeReviewer, TradeReview
from .memory import TradingMemory, MemoryRecord


class TradingCopilot:
    """Central engine that coordinates all AI Trading Copilot capabilities.

    Integrates market analysis, position explanation, risk monitoring,
    trade planning, trade review, and trading memory into a unified
    interface for trader interaction.
    """

    def __init__(self):
        self.market_analyst = MarketAnalyst()
        self.position_assistant = PositionAssistant()
        self.risk_monitor = RiskMonitor()
        self.trade_planner = TradePlanner()
        self.trade_reviewer = TradeReviewer()
        self.memory = TradingMemory()

    # ------------------------------------------------------------------
    # Market Analysis
    # ------------------------------------------------------------------

    def analyze_market(
        self,
        symbol: str,
        price_momentum: float = 0.0,
        volume_confirmation: float = 0.0,
        volatility: float = 0.0,
        sector_strength: float = 0.0,
        news_sentiment: Optional[float] = None,
    ) -> MarketAnalysis:
        """Perform multi-factor market analysis for a symbol."""
        return self.market_analyst.analyze(
            symbol=symbol,
            price_momentum=price_momentum,
            volume_confirmation=volume_confirmation,
            volatility=volatility,
            sector_strength=sector_strength,
            news_sentiment=news_sentiment,
        )

    # ------------------------------------------------------------------
    # Position Analysis
    # ------------------------------------------------------------------

    def analyze_position(
        self,
        symbol: str,
        exposure: float,
        momentum: float = 0.0,
        valuation_high: bool = False,
        sector_concentration: float = 0.0,
        volatility: float = 0.0,
    ) -> PositionAnalysis:
        """Analyse a single position and return commentary."""
        return self.position_assistant.analyze_position(
            symbol=symbol,
            exposure=exposure,
            momentum=momentum,
            valuation_high=valuation_high,
            sector_concentration=sector_concentration,
            volatility=volatility,
        )

    def portfolio_overview(
        self, positions: List[PositionAnalysis]
    ) -> dict:
        """Generate portfolio-level summary."""
        return self.position_assistant.portfolio_overview(positions)

    # ------------------------------------------------------------------
    # Risk Monitoring
    # ------------------------------------------------------------------

    def check_risks(
        self,
        exposure: float = 0.0,
        drawdown: float = 0.0,
        volatility: float = 0.0,
        sector_concentration: float = 0.0,
    ) -> List[RiskAlert]:
        """Run risk checks and return triggered alerts."""
        return self.risk_monitor.check(
            exposure=exposure,
            drawdown=drawdown,
            volatility=volatility,
            sector_concentration=sector_concentration,
        )

    # ------------------------------------------------------------------
    # Trade Planning
    # ------------------------------------------------------------------

    def plan_trade(
        self,
        symbol: str,
        current_price: float,
        signal: float,
        risk_limit: float = 1.0,
        strategy_name: str = "",
    ) -> TradePlan:
        """Generate a trade execution plan."""
        return self.trade_planner.plan(
            symbol=symbol,
            current_price=current_price,
            signal=signal,
            risk_limit=risk_limit,
            strategy_name=strategy_name,
        )

    # ------------------------------------------------------------------
    # Trade Review
    # ------------------------------------------------------------------

    def review_trade(
        self,
        trade_id: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        planned_action: str = "",
        actual_action: str = "",
    ) -> TradeReview:
        """Perform post-trade review."""
        return self.trade_reviewer.review(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            planned_action=planned_action,
            actual_action=actual_action,
        )

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def remember(
        self,
        trade_id: str,
        symbol: str,
        action: str,
        decision_reason: str,
        outcome: str = "",
        pnl_pct: float = 0.0,
        market_environment: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Record a trade in the trading memory."""
        record = MemoryRecord(
            trade_id=trade_id,
            symbol=symbol,
            action=action,
            decision_reason=decision_reason,
            outcome=outcome,
            pnl_pct=pnl_pct,
            market_environment=market_environment or {},
        )
        self.memory.save(record)
        return record

    def memory_history(self) -> List[MemoryRecord]:
        """Return full trade memory history."""
        return self.memory.history()

    def memory_win_rate(self) -> float:
        """Return win rate from trading memory."""
        return self.memory.win_rate()

    # ------------------------------------------------------------------
    # Legacy / Generic interface
    # ------------------------------------------------------------------

    def analyze(self, context: str) -> dict:
        """Generic analysis entry point (legacy / conversation bridge).

        Returns the context wrapped as an analysis result.
        """
        return {"analysis": context}

    def suggest(self, signal: str) -> dict:
        """Generic suggestion entry point (legacy / conversation bridge).

        Returns the signal as an action suggestion.
        """
        return {"action": signal}
