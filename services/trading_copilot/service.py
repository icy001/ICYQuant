"""Trading Copilot Service – high-level API for AI Trading Copilot."""

from typing import Any, Dict, List, Optional

from .copilot import TradingCopilot
from .market_analysis import MarketAnalysis
from .position import PositionAnalysis
from .risk_alert import RiskAlert
from .trade_plan import TradePlan
from .review import TradeReview
from .memory import MemoryRecord


class TradingCopilotService:
    """Service layer that wraps TradingCopilot for application use.

    Provides a clean, high-level API for trader-facing features:
    market analysis, position analysis, risk alerts, trade planning,
    trade review, and trading memory access.
    """

    def __init__(self, copilot: Optional[TradingCopilot] = None):
        self.copilot = copilot or TradingCopilot()

    # ------------------------------------------------------------------
    # Conversation / Generic interface
    # ------------------------------------------------------------------

    def ask(self, context: str) -> dict:
        """Process a natural-language-like query through the copilot."""
        return self.copilot.analyze(context)

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
        return self.copilot.analyze_market(
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
        return self.copilot.analyze_position(
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
        return self.copilot.portfolio_overview(positions)

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
        return self.copilot.check_risks(
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
        return self.copilot.plan_trade(
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
        return self.copilot.review_trade(
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
        return self.copilot.remember(
            trade_id=trade_id,
            symbol=symbol,
            action=action,
            decision_reason=decision_reason,
            outcome=outcome,
            pnl_pct=pnl_pct,
            market_environment=market_environment,
        )

    def memory_history(self) -> List[MemoryRecord]:
        return self.copilot.memory_history()

    def memory_win_rate(self) -> float:
        return self.copilot.memory_win_rate()
