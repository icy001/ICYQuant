"""Performance Attribution Engine – decompose trade returns into sources."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class AttributionResult:
    """Decomposed performance attribution for a trade or portfolio."""

    trade_id: str = ""
    total_pnl_pct: float = 0.0

    # Attribution components
    alpha: float = 0.0  # Strategy-specific edge
    market_beta: float = 0.0  # Market movement contribution
    sector: float = 0.0  # Sector-specific contribution
    timing: float = 0.0  # Entry/exit timing contribution
    execution: float = 0.0  # Execution quality contribution
    residual: float = 0.0  # Unexplained portion

    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "total_pnl_pct": self.total_pnl_pct,
            "alpha": self.alpha,
            "market_beta": self.market_beta,
            "sector": self.sector,
            "timing": self.timing,
            "execution": self.execution,
            "residual": self.residual,
            "confidence": self.confidence,
        }


class AttributionEngine:
    """Decomposes trade returns into their constituent sources.

    Attribution categories:
    - Alpha: strategy-specific edge (residual after other factors)
    - Market Beta: contribution from broad market movement
    - Sector: contribution from sector/industry movement
    - Timing: contribution from entry/exit timing decisions
    - Execution: cost/benefit from execution quality (slippage)
    - Residual: unexplained portion
    """

    def analyze(self, trade: TradeResult,
                market_return_pct: float = 0.0,
                sector_return_pct: float = 0.0,
                beta: float = 1.0) -> dict:
        """Quick analysis returning a summary dict."""
        result = self.analyze_detailed(trade, market_return_pct,
                                       sector_return_pct, beta)
        return {
            "trade_id": result.trade_id,
            "total_pnl_pct": result.total_pnl_pct,
            "alpha": result.alpha,
            "market_beta": result.market_beta,
            "sector": result.sector,
            "timing": result.timing,
            "execution": result.execution,
        }

    def analyze_detailed(
        self,
        trade: TradeResult,
        market_return_pct: float = 0.0,
        sector_return_pct: float = 0.0,
        beta: float = 1.0,
    ) -> AttributionResult:
        """Full performance attribution analysis."""
        result = AttributionResult(
            trade_id=trade.trade_id,
            total_pnl_pct=trade.pnl_pct,
        )

        # 1. Market Beta: broad market contribution
        result.market_beta = round(beta * market_return_pct, 2)

        # 2. Sector: sector-specific contribution (ex-market)
        result.sector = round(sector_return_pct - market_return_pct, 2)

        # 3. Execution: cost from slippage
        avg_slippage = (abs(trade.entry_slippage_bps) + abs(trade.exit_slippage_bps)) / 2 / 100
        result.execution = round(-avg_slippage, 2)

        # 4. Timing: residual from entry/exit vs market
        result.timing = self._estimate_timing(trade, market_return_pct)

        # 5. Alpha: strategy-specific edge (residual)
        explained = (result.market_beta + result.sector +
                     result.execution + result.timing)
        result.alpha = round(trade.pnl_pct - explained, 2)

        # 6. Residual
        result.residual = round(trade.pnl_pct - result.alpha -
                                result.market_beta - result.sector -
                                result.timing - result.execution, 2)

        result.confidence = min(0.9, 0.4 + abs(trade.pnl_pct) * 0.05)

        return result

    def analyze_batch(
        self,
        trades: List[TradeResult],
        market_returns: Optional[List[float]] = None,
        sector_returns: Optional[List[float]] = None,
        betas: Optional[List[float]] = None,
    ) -> List[AttributionResult]:
        """Attribution analysis for a batch of trades."""
        results = []
        for i, trade in enumerate(trades):
            mr = market_returns[i] if market_returns and i < len(market_returns) else 0.0
            sr = sector_returns[i] if sector_returns and i < len(sector_returns) else 0.0
            b = betas[i] if betas and i < len(betas) else 1.0
            results.append(self.analyze_detailed(trade, mr, sr, b))
        return results

    def aggregate(self, results: List[AttributionResult]) -> dict:
        """Aggregate attribution across multiple trades."""
        if not results:
            return {"total_trades": 0, "total_pnl_pct": 0.0,
                    "alpha": 0.0, "market_beta": 0.0}

        total_pnl = sum(r.total_pnl_pct for r in results)
        total_alpha = sum(r.alpha for r in results)
        total_market = sum(r.market_beta for r in results)
        total_sector = sum(r.sector for r in results)
        total_timing = sum(r.timing for r in results)
        total_execution = sum(r.execution for r in results)

        return {
            "total_trades": len(results),
            "total_pnl_pct": round(total_pnl, 2),
            "alpha_contribution": round(total_alpha, 2),
            "alpha_pct": round(total_alpha / total_pnl * 100, 1) if total_pnl != 0 else 0.0,
            "market_contribution": round(total_market, 2),
            "market_pct": round(total_market / total_pnl * 100, 1) if total_pnl != 0 else 0.0,
            "sector_contribution": round(total_sector, 2),
            "timing_contribution": round(total_timing, 2),
            "execution_contribution": round(total_execution, 2),
            "execution_cost_bps": round(-total_execution * 100, 1),
        }

    def _estimate_timing(self, trade: TradeResult,
                         market_return_pct: float) -> float:
        """Estimate timing contribution.

        Positive timing: we entered before market went up / exited before market went down.
        Simplified model based on entry/exit slippage vs market movement.
        """
        # If market went up and we had positive entry slippage, timing was good
        # (entered before the move)
        timing = 0.0
        if market_return_pct > 0 and trade.entry_slippage_bps < 0:
            timing += abs(market_return_pct) * 0.3
        elif market_return_pct < 0 and trade.entry_slippage_bps > 0:
            timing += abs(market_return_pct) * 0.3
        elif market_return_pct > 0 and trade.entry_slippage_bps > 0:
            timing -= abs(market_return_pct) * 0.1
        elif market_return_pct < 0 and trade.entry_slippage_bps < 0:
            timing -= abs(market_return_pct) * 0.1

        return round(timing, 2)
