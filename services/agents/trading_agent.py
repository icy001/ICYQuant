"""Trading Decision Agent - core trading decision maker.

Generates trading proposals based on inputs from:
- Market Agent (regime, trend, volatility)
- Alpha Model (signals, scores)
- Knowledge Graph (events, relations)
- Portfolio State (current holdings)

Produces trading intentions (BUY/SELL/HOLD) that must pass through
Risk Agent before execution.
"""

import time
import logging
from typing import Any, Dict, List, Optional

from .agent_base import (
    BaseAgent, Observation, Analysis, Decision, DecisionAction,
)

logger = logging.getLogger(__name__)


class TradingAgent(BaseAgent):
    """Trading Decision Agent.

    Core decision-making agent that evaluates market conditions,
    alpha signals, and portfolio state to generate trading proposals.

    Does NOT directly execute trades - proposals go through:
    1. Risk Agent (risk approval)
    2. Portfolio Agent (portfolio fit)
    3. Execution Agent (order execution)
    """

    agent_type = "trading_agent"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name, config=config)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.max_position_size = self.config.get("max_position_size", 10.0)
        self._alpha_signals: Dict[str, Dict[str, Any]] = {}
        self._market_state: Dict[str, Any] = {}
        self._pending_proposals: List[Decision] = []
        self._proposal_history: List[Decision] = []

        # Register message handlers
        self.communicator.register_handler("MARKET_STATE", self._on_market_state)
        self.communicator.register_handler("ALPHA_SIGNAL", self._on_alpha_signal)
        self.communicator.register_handler("PORTFOLIO_STATE", self._on_portfolio_state)
        self.communicator.register_handler("RISK_DECISION", self._on_risk_decision)
        self.communicator.register_handler("KNOWLEDGE_EVENT", self._on_knowledge_event)

    # ── Message Handlers ────────────────────────────────────────

    def _on_market_state(self, data: Dict[str, Any]) -> None:
        """Handle market state update from Market Agent."""
        self._market_state = data
        self.memory.set_working("market_state", data)
        self.memory.remember_episode(
            content=data,
            context={"source": "market_agent"},
            tags=["market", data.get("regime", "unknown")],
        )

    def _on_alpha_signal(self, data: Dict[str, Any]) -> None:
        """Handle alpha signal updates."""
        symbol = data.get("symbol", "")
        if symbol:
            self._alpha_signals[symbol] = data

    def _on_portfolio_state(self, data: Dict[str, Any]) -> None:
        """Handle portfolio state update."""
        self.memory.set_working("portfolio_state", data)

    def _on_risk_decision(self, data: Dict[str, Any]) -> None:
        """Handle risk agent decision on a proposal."""
        proposal_id = data.get("proposal_id", "")
        decision = data.get("decision", "rejected")
        for p in self._pending_proposals:
            if p.decision_id == proposal_id:
                p.status = decision
                p.approved_by = "risk_agent"
                break

        # Learn from the risk decision
        self.memory.learn_from_outcome(
            decision={"proposal_id": proposal_id, "data": data},
            outcome=decision,
            reward=1.0 if decision == "approved" else -0.3,
            context={"source": "risk_agent"},
        )

    def _on_knowledge_event(self, data: Dict[str, Any]) -> None:
        """Handle events from knowledge graph (e.g., earnings surprise)."""
        self.memory.remember_episode(
            content=data,
            context={"source": "knowledge_graph"},
            tags=["knowledge", data.get("event_type", "unknown")],
        )

    # ── Main Agent Loop ─────────────────────────────────────────

    def observe(self) -> Optional[Observation]:
        """Observe current state from all sources."""
        market = self._market_state
        alpha = self._alpha_signals
        portfolio = self.memory.get_working("portfolio_state", {})

        return Observation(
            source=self.name,
            data={
                "market": market,
                "alpha_signals": dict(alpha),
                "portfolio": portfolio,
                "pending_proposals": len(self._pending_proposals),
            },
            tags=["trading", market.get("regime", "unknown")],
        )

    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze observations and generate trading signals."""
        if observation is None:
            return None

        data = observation.data
        market = data.get("market", {})
        alpha = data.get("alpha_signals", {})
        regime = market.get("regime", "unknown")

        signals = []
        confidence = 0.5

        # Analyze alpha signals
        for symbol, signal_data in alpha.items():
            score = signal_data.get("score", 0)
            signal_confidence = signal_data.get("confidence", 0.5)

            if abs(score) > 0.3 and signal_confidence >= self.min_confidence:
                action = "BUY" if score > 0 else "SELL"
                signals.append({
                    "symbol": symbol,
                    "action": action,
                    "alpha_score": score,
                    "confidence": signal_confidence,
                    "source": "alpha_model",
                    "reason": signal_data.get("reason", "Alpha signal"),
                })
                confidence = max(confidence, signal_confidence)

        # Market regime adjustments
        if regime in ("risk_off", "trending_down", "crisis"):
            for s in signals:
                if s["action"] == "BUY":
                    s["confidence"] *= 0.7  # Reduce buy confidence in risk-off
                    s["reason"] += " (adjusted for risk-off)"

        # Knowledge graph events
        recent_events = self.memory.recall_episodes(tags=["knowledge"], limit=10)
        for event in recent_events:
            event_type = event.content.get("event_type", "")
            affected = event.content.get("affected_symbols", [])
            for symbol in affected:
                existing = next((s for s in signals if s["symbol"] == symbol), None)
                if existing is None:
                    signals.append({
                        "symbol": symbol,
                        "action": "BUY" if event.content.get("impact", "positive") == "positive" else "SELL",
                        "confidence": event.content.get("confidence", 0.5),
                        "source": "knowledge_graph",
                        "reason": f"Event: {event_type}",
                    })

        return Analysis(
            agent=self.name,
            summary=f"Generated {len(signals)} trading signals from alpha + market data",
            metrics={
                "regime": regime,
                "signal_count": len(signals),
                "alpha_signal_count": len(alpha),
            },
            signals=signals,
            confidence=confidence,
        )

    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Convert analysis signals into a trading proposal.

        Selects the highest-confidence signal that meets thresholds.
        """
        if analysis is None or not analysis.signals:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol="",
                confidence=0.5,
                reason=["No actionable signals"],
            )

        # Sort signals by confidence
        signals = sorted(analysis.signals, key=lambda s: s["confidence"], reverse=True)

        # Pick the best signal
        best = signals[0]
        if best["confidence"] < self.min_confidence:
            return Decision(
                agent=self.name,
                action=DecisionAction.HOLD,
                symbol=best.get("symbol", ""),
                confidence=best["confidence"],
                reason=[f"Best signal confidence ({best['confidence']:.2f}) below threshold ({self.min_confidence})"],
            )

        action_map = {"BUY": DecisionAction.BUY, "SELL": DecisionAction.SELL, "HOLD": DecisionAction.HOLD}
        action = action_map.get(best.get("action", "HOLD"), DecisionAction.HOLD)

        decision = Decision(
            agent=self.name,
            action=action,
            symbol=best.get("symbol", ""),
            size=min(best.get("confidence", 0.5) * self.max_position_size, self.max_position_size),
            confidence=best["confidence"],
            reason=[
                best.get("reason", "Alpha signal"),
                f"Source: {best.get('source', 'unknown')}",
                f"Market regime: {analysis.metrics.get('regime', 'unknown')}",
            ],
            metadata={
                "alpha_score": best.get("alpha_score", 0),
                "source": best.get("source", ""),
            },
        )

        # Store as pending proposal
        self._pending_proposals.append(decision)
        self._proposal_history.append(decision)

        # Send proposal to Risk Agent for approval
        self.send_to(
            recipient="risk_agent",
            event="TRADE_PROPOSAL",
            data=decision.to_dict(),
        )

        # Also notify Portfolio Agent
        self.send_to(
            recipient="portfolio_agent",
            event="TRADE_PROPOSAL_NOTICE",
            data=decision.to_dict(),
        )

        logger.info(
            "[%s] Proposal: %s %s (%.1f%%, conf=%.2f)",
            self.name, decision.action.value, decision.symbol,
            decision.size, decision.confidence,
        )

        return decision

    # ── Alpha Signal Input ──────────────────────────────────────

    def ingest_alpha_signal(
        self,
        symbol: str,
        score: float,
        confidence: float = 0.5,
        reason: str = "",
        **kwargs,
    ) -> None:
        """Ingest an alpha signal for consideration."""
        self._alpha_signals[symbol] = {
            "symbol": symbol,
            "score": score,
            "confidence": confidence,
            "reason": reason,
            "timestamp": time.time(),
            **kwargs,
        }
        logger.debug("[%s] Alpha signal: %s score=%.3f", self.name, symbol, score)

    def get_proposals(
        self, status: str = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get trading proposals with optional status filter."""
        proposals = self._proposal_history
        if status:
            proposals = [p for p in proposals if p.status == status]
        return [p.to_dict() for p in proposals[-limit:]]

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get currently pending proposals."""
        return [p.to_dict() for p in self._pending_proposals if p.status == "pending"]

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update({
            "alpha_signals": len(self._alpha_signals),
            "pending_proposals": len(self._pending_proposals),
            "total_proposals": len(self._proposal_history),
            "market_state": self._market_state,
        })
        return report
