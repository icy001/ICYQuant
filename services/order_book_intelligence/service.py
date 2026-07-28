"""Order Book Intelligence Service — unified microstructure analysis API.

Orchestrates all 10 order book intelligence engines:
  - OrderBookBuilder: Real-time order book maintenance
  - OrderImbalanceAnalyzer: Bid/ask imbalance detection
  - LiquidityWallDetector: Large resting order wall detection
  - HiddenLiquidityEstimator: Dark pool & hidden order estimation
  - IcebergDetector: Iceberg order pattern detection
  - LargeOrderTracker: Institutional block order tracking
  - OrderFlowToxicityAnalyzer: VPIN & toxicity analysis
  - QueuePositionEstimator: Fill time & queue position prediction
  - MicrostructureAlphaGenerator: Multi-signal alpha synthesis
  - OrderBookMemory: Microstructure knowledge base

Provides a single entry point for real-time market microstructure
intelligence and execution optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from services.order_book_intelligence.snapshot import (
    BookLevel,
    BookSide,
    OrderBookBuilder,
    OrderBookSnapshot,
)
from services.order_book_intelligence.imbalance import (
    ImbalanceDirection,
    ImbalanceSignal,
    OrderImbalanceAnalyzer,
)
from services.order_book_intelligence.liquidity_wall import (
    LiquidityWall,
    LiquidityWallDetector,
    WallDetectionResult,
    WallStrength,
    WallType,
)
from services.order_book_intelligence.hidden_liquidity import (
    HiddenLiquidityEstimate,
    HiddenLiquidityEstimator,
)
from services.order_book_intelligence.iceberg import (
    IcebergDetection,
    IcebergDetector,
    IcebergStatus,
)
from services.order_book_intelligence.large_order import (
    InstitutionActivity,
    LargeOrderTracker,
    OrderCategory,
)
from services.order_book_intelligence.toxicity import (
    OrderFlowToxicityAnalyzer,
    ToxicityAssessment,
    ToxicityLevel,
)
from services.order_book_intelligence.queue import (
    QueueEstimate,
    QueuePositionEstimator,
)
from services.order_book_intelligence.alpha import (
    MicroAlphaSignal,
    MicrostructureAlphaGenerator,
    SignalDirection,
    SignalStrength,
)
from services.order_book_intelligence.memory import (
    MicrostructureEvent,
    OrderBookMemory,
)


# ---------------------------------------------------------------------------
# Unified Result
# ---------------------------------------------------------------------------


@dataclass
class MicrostructureReport:
    """Complete microstructure intelligence report.

    Attributes:
        snapshot: Current order book snapshot.
        imbalance: Order imbalance analysis.
        walls: Liquidity wall detection.
        hidden_liquidity: Hidden liquidity estimate.
        icebergs: Iceberg order detections.
        institutional_activity: Large order activity.
        toxicity: Order flow toxicity assessment.
        queue_estimate: Queue position estimate.
        alpha: Microstructure alpha signal.
        summary: Aggregated summary dict.
        timestamp: Report generation time.
    """

    snapshot: Optional[OrderBookSnapshot] = None
    imbalance: Optional[ImbalanceSignal] = None
    walls: Optional[WallDetectionResult] = None
    hidden_liquidity: Optional[HiddenLiquidityEstimate] = None
    icebergs: list[IcebergDetection] = field(default_factory=list)
    institutional_activity: Optional[InstitutionActivity] = None
    toxicity: Optional[ToxicityAssessment] = None
    queue_estimate: Optional[QueueEstimate] = None
    alpha: Optional[MicroAlphaSignal] = None
    summary: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        d: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
        }
        if self.snapshot:
            d["snapshot"] = self.snapshot.to_dict()
        if self.imbalance:
            d["imbalance"] = self.imbalance.to_dict()
        if self.walls:
            d["walls"] = self.walls.to_dict()
        if self.hidden_liquidity:
            d["hidden_liquidity"] = self.hidden_liquidity.to_dict()
        if self.icebergs:
            d["icebergs"] = [i.to_dict() for i in self.icebergs]
        if self.institutional_activity:
            d["institutional_activity"] = self.institutional_activity.to_dict()
        if self.toxicity:
            d["toxicity"] = self.toxicity.to_dict()
        if self.alpha:
            d["alpha"] = self.alpha.to_dict()
        if self.summary:
            d["summary"] = self.summary
        return d


# ---------------------------------------------------------------------------
# OrderBookIntelligenceService
# ---------------------------------------------------------------------------


class OrderBookIntelligenceService:
    """Unified order book intelligence service.

    Orchestrates the full microstructure analysis pipeline:
    snapshot → imbalance → walls → hidden liquidity → icebergs →
    large orders → toxicity → queue → alpha.

    Attributes:
        analyzer: Order imbalance analyzer (primary entry).
        book_builder: Order book snapshot builder.
        wall_detector: Liquidity wall detector.
        hidden_estimator: Hidden liquidity estimator.
        iceberg_detector: Iceberg order detector.
        order_tracker: Large order tracker.
        toxicity_analyzer: Order flow toxicity analyzer.
        queue_estimator: Queue position estimator.
        alpha_generator: Microstructure alpha generator.
        memory: Order book memory.
    """

    def __init__(
        self,
    ) -> None:
        """Initialize the order book intelligence service."""
        self.analyzer = OrderImbalanceAnalyzer()
        self.book_builder = OrderBookBuilder()
        self.wall_detector = LiquidityWallDetector()
        self.hidden_estimator = HiddenLiquidityEstimator()
        self.iceberg_detector = IcebergDetector()
        self.order_tracker = LargeOrderTracker()
        self.toxicity_analyzer = OrderFlowToxicityAnalyzer()
        self.queue_estimator = QueuePositionEstimator()
        self.alpha_generator = MicrostructureAlphaGenerator()
        self.memory = OrderBookMemory()

    # ------------------------------------------------------------------
    # Simple Analysis (spec-compatible)
    # ------------------------------------------------------------------

    def analyze(
        self,
        bid: float,
        ask: float,
    ) -> float:
        """Simple bid/ask imbalance analysis.

        Args:
            bid: Bid-side volume.
            ask: Ask-side volume.

        Returns:
            Imbalance score (-1 to +1).
        """
        return self.analyzer.calculate(bid, ask).score

    # ------------------------------------------------------------------
    # Comprehensive Analysis
    # ------------------------------------------------------------------

    def analyze_snapshot(
        self,
        snapshot: OrderBookSnapshot,
        trades: Optional[list[dict[str, Any]]] = None,
    ) -> MicrostructureReport:
        """Run full microstructure analysis on an order book snapshot.

        Args:
            snapshot: Current order book snapshot.
            trades: Recent trades for hidden liquidity and toxicity.

        Returns:
            MicrostructureReport with all engine results.
        """
        # 1. Imbalance
        imbalance = self.analyzer.calculate_from_snapshot(snapshot)

        # 2. Liquidity Walls
        walls = self.wall_detector.detect_from_snapshot(snapshot)

        # 3. Hidden Liquidity
        trades = trades or []
        hidden = self.hidden_estimator.estimate(trades)

        # 4. Icebergs
        icebergs = self.iceberg_detector.detect(trades)

        # 5. Large Orders
        for trade in trades[-20:]:
            self.order_tracker.track(trade)
        inst_activity = self.order_tracker.analyze_activity()

        # 6. Toxicity
        toxicity = self.toxicity_analyzer.assess(trades)

        # 7. Queue Position (estimate for best bid)
        best_bid_vol = snapshot.best_bid.volume if snapshot.best_bid else 0.0
        queue_est = self.queue_estimator.estimate(
            queue_size=best_bid_vol,
            trade_rate=best_bid_vol / 10.0 if best_bid_vol > 0 else 100.0,
        )

        # 8. Alpha Synthesis
        alpha = self.alpha_generator.synthesize(
            imbalance=imbalance.score,
            toxicity=toxicity.toxicity_score,
            wall_imbalance=walls.wall_imbalance,
            iceberg_confidence=max(
                (i.confidence for i in icebergs), default=0.0
            ),
            hidden_liquidity_conf=hidden.overall_confidence,
            institutional_flow=inst_activity.accumulation_score,
        )

        # 9. Memory
        self.memory.save(snapshot)
        if imbalance.is_extreme:
            self.memory.record(
                MicrostructureEvent.IMBALANCE_EXTREME,
                data={"imbalance_score": imbalance.score},
                price=snapshot.mid_price,
            )
        if walls.significant_walls:
            self.memory.record(
                MicrostructureEvent.WALL_DETECTED,
                data={"walls": [w.to_dict() for w in walls.significant_walls]},
                price=snapshot.mid_price,
            )
        self.memory.record_alpha_signal(
            alpha_score=alpha.alpha_score,
            direction=alpha.direction.value,
            strength=alpha.strength.value,
            confidence=alpha.confidence,
        )

        # Summary
        summary = self._build_summary(imbalance, walls, toxicity, alpha, inst_activity)

        return MicrostructureReport(
            snapshot=snapshot,
            imbalance=imbalance,
            walls=walls,
            hidden_liquidity=hidden,
            icebergs=icebergs,
            institutional_activity=inst_activity,
            toxicity=toxicity,
            queue_estimate=queue_est,
            alpha=alpha,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Summary Builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        imbalance: ImbalanceSignal,
        walls: WallDetectionResult,
        toxicity: ToxicityAssessment,
        alpha: MicroAlphaSignal,
        inst_activity: InstitutionActivity,
    ) -> dict[str, Any]:
        """Build a concise summary from analysis results."""
        return {
            "imbalance": {
                "direction": imbalance.direction.value,
                "score": round(imbalance.score, 4),
            },
            "walls": {
                "count": len(walls.walls),
                "dominant_side": walls.dominant_side.value if walls.dominant_side else "none",
                "significant": len(walls.significant_walls),
            },
            "toxicity": {
                "level": toxicity.toxicity_level.value,
                "score": round(toxicity.toxicity_score, 4),
            },
            "alpha": {
                "direction": alpha.direction.value,
                "score": round(alpha.alpha_score, 4),
                "is_actionable": alpha.is_actionable,
            },
            "institutional": {
                "activity_level": inst_activity.activity_level.value,
                "net_flow": round(inst_activity.net_flow, 2),
            },
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_analyze(
        self,
        bid_volume: float,
        ask_volume: float,
        vpin: float = 0.3,
    ) -> dict[str, Any]:
        """Quick microstructure analysis with minimal input.

        Args:
            bid_volume: Bid-side volume.
            ask_volume: Ask-side volume.
            vpin: VPIN toxicity estimate.

        Returns:
            Dict with imbalance, alpha, and summary.
        """
        imb = self.analyzer.calculate(bid_volume, ask_volume)
        alpha = self.alpha_generator.quick_generate(
            imbalance=imb.score,
            toxicity=vpin,
        )
        return {
            "imbalance": round(imb.score, 4),
            "direction": imb.direction.value,
            "alpha": alpha["alpha"],
            "alpha_direction": alpha["direction"],
        }

    def memory_status(self) -> dict[str, Any]:
        """Get microstructure memory status."""
        return self.memory.quick_status()

    def clear_all(self) -> None:
        """Reset all engines."""
        self.analyzer.clear()
        self.book_builder.clear()
        self.wall_detector.clear()
        self.hidden_estimator.clear()
        self.iceberg_detector.clear()
        self.order_tracker.clear()
        self.toxicity_analyzer.clear()
        self.queue_estimator.clear()
        self.alpha_generator.clear()
        self.memory.clear()
