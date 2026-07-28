"""Liquidity Wall Detector — large resting order detection in the order book.

Identifies significant bid/ask walls that act as support/resistance,
detects wall strength, durability, and predicts potential break/defend
scenarios for execution optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from services.order_book_intelligence.snapshot import (
    BookSide,
    OrderBookSnapshot,
    PriceLevel,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WallStrength(str, Enum):
    """Liquidity wall strength classification."""

    MINOR = "minor"  # 2-5x average level volume
    MODERATE = "moderate"  # 5-10x
    MAJOR = "major"  # 10-20x
    FORTRESS = "fortress"  # > 20x


class WallType(str, Enum):
    """Liquidity wall type."""

    SUPPORT = "support"  # Bid wall (buy support)
    RESISTANCE = "resistance"  # Ask wall (sell resistance)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class LiquidityWall:
    """A detected liquidity wall.

    Attributes:
        price: Wall price level.
        volume: Wall volume.
        side: BID or ASK.
        strength: Wall strength classification.
        depth_distance: Distance from best bid/ask in price units.
        notional: Notional value of the wall.
        percentage_of_book: Wall volume as percentage of side total.
        wall_type: SUPPORT (bid) or RESISTANCE (ask).
        timestamp: Detection timestamp.
    """

    price: float
    volume: float
    side: BookSide
    strength: WallStrength = WallStrength.MINOR
    depth_distance: float = 0.0
    notional: float = 0.0
    percentage_of_book: float = 0.0
    wall_type: WallType = WallType.SUPPORT
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_bid_wall(self) -> bool:
        """Whether this is a bid-side wall."""
        return self.side == BookSide.BID

    @property
    def is_ask_wall(self) -> bool:
        """Whether this is an ask-side wall."""
        return self.side == BookSide.ASK

    @property
    def is_significant(self) -> bool:
        """Whether wall is major or fortress strength."""
        return self.strength in (WallStrength.MAJOR, WallStrength.FORTRESS)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "price": self.price,
            "volume": round(self.volume, 2),
            "side": self.side.value,
            "strength": self.strength.value,
            "notional": round(self.notional, 2),
            "pct_of_book": round(self.percentage_of_book, 4),
            "is_significant": self.is_significant,
        }


@dataclass
class WallDetectionResult:
    """Complete liquidity wall detection result.

    Attributes:
        walls: List of detected walls.
        bid_walls: Bid-side walls (sorted by strength).
        ask_walls: Ask-side walls (sorted by strength).
        dominant_side: Which side has stronger walls.
        wall_imbalance: Imbalance in wall strength (bid - ask normalized).
        price_zone: Predicted support/resistance zone.
        timestamp: Detection time.
    """

    walls: list[LiquidityWall]
    bid_walls: list[LiquidityWall] = field(default_factory=list)
    ask_walls: list[LiquidityWall] = field(default_factory=list)
    dominant_side: Optional[WallType] = None
    wall_imbalance: float = 0.0
    price_zone: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def strongest_wall(self) -> Optional[LiquidityWall]:
        """The strongest wall detected."""
        if not self.walls:
            return None
        return max(self.walls, key=lambda w: (w.strength_weight, w.volume))

    @property
    def bid_wall_count(self) -> int:
        """Number of bid walls."""
        return len(self.bid_walls)

    @property
    def ask_wall_count(self) -> int:
        """Number of ask walls."""
        return len(self.ask_walls)

    @property
    def significant_walls(self) -> list[LiquidityWall]:
        """Walls that are major or fortress strength."""
        return [w for w in self.walls if w.is_significant]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "wall_count": len(self.walls),
            "bid_wall_count": self.bid_wall_count,
            "ask_wall_count": self.ask_wall_count,
            "dominant_side": self.dominant_side.value if self.dominant_side else "none",
            "wall_imbalance": round(self.wall_imbalance, 4),
            "significant_walls": [w.to_dict() for w in self.significant_walls],
            "all_walls": [w.to_dict() for w in self.walls],
        }


# ---------------------------------------------------------------------------
# LiquidityWallDetector
# ---------------------------------------------------------------------------


class LiquidityWallDetector:
    """Real-time liquidity wall detection engine.

    Scans order book levels for abnormally large resting orders (walls).
    Classifies wall strength, tracks wall persistence over time, and
    predicts support/resistance zones for execution routing.

    Attributes:
        avg_volume_multiplier: Multiplier over average to flag as wall.
        min_wall_volume: Minimum absolute volume for a wall.
        depth_levels: Number of book levels to scan per side.
        history: Past detection results.
    """

    STRENGTH_MULTIPLIERS: dict[WallStrength, float] = {
        WallStrength.MINOR: 2.0,
        WallStrength.MODERATE: 5.0,
        WallStrength.MAJOR: 10.0,
        WallStrength.FORTRESS: 20.0,
    }

    def __init__(
        self,
        avg_volume_multiplier: float = 3.0,
        min_wall_volume: float = 1000.0,
        depth_levels: int = 20,
    ) -> None:
        """Initialize the liquidity wall detector.

        Args:
            avg_volume_multiplier: How many times average to flag as wall.
            min_wall_volume: Minimum absolute volume threshold.
            depth_levels: How many levels to scan per side.
        """
        self.avg_volume_multiplier = avg_volume_multiplier
        self.min_wall_volume = min_wall_volume
        self.depth_levels = depth_levels
        self.history: list[WallDetectionResult] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def detect(
        self,
        levels: list[dict[str, Any]],
        side: BookSide = BookSide.BID,
        threshold: Optional[float] = None,
    ) -> list[LiquidityWall]:
        """Detect walls from a list of price level dicts.

        Args:
            levels: List of dicts with 'price' and 'volume' keys.
            side: BID or ASK.
            threshold: Override volume threshold for wall detection.

        Returns:
            List of LiquidityWall objects sorted by strength descending.
        """
        if not levels:
            return []

        threshold = threshold or self.min_wall_volume
        volumes = [l["volume"] for l in levels]
        # Use median as baseline to avoid the wall itself skewing the average
        sorted_vols = sorted(volumes)
        n = len(sorted_vols)
        if n > 0:
            avg_vol = sorted_vols[n // 2] if n % 2 == 1 else (sorted_vols[n // 2 - 1] + sorted_vols[n // 2]) / 2
        else:
            avg_vol = 0.0

        walls = []
        for i, level_dict in enumerate(levels):
            price = level_dict["price"]
            volume = level_dict["volume"]

            # Must exceed both absolute threshold and multiplier of average
            if volume < threshold and volume < avg_vol * self.avg_volume_multiplier:
                continue

            # Classify strength
            strength = self._classify_strength(volume, avg_vol)

            # Distance from top of book
            best_price = levels[0]["price"] if levels else price
            depth_distance = abs(price - best_price)

            # Percentage of side total
            side_total = sum(l["volume"] for l in levels)
            pct_of_book = volume / max(side_total, 1)

            wall_type = WallType.SUPPORT if side == BookSide.BID else WallType.RESISTANCE

            walls.append(
                LiquidityWall(
                    price=price,
                    volume=volume,
                    side=side,
                    strength=strength,
                    depth_distance=depth_distance,
                    notional=price * volume,
                    percentage_of_book=pct_of_book,
                    wall_type=wall_type,
                )
            )

        # Sort by strength (fortress first) then volume
        walls.sort(key=lambda w: (-w.strength_weight, -w.volume))
        return walls

    def detect_from_snapshot(
        self,
        snapshot: OrderBookSnapshot,
        threshold: Optional[float] = None,
    ) -> WallDetectionResult:
        """Detect all walls from an order book snapshot.

        Args:
            snapshot: Order book snapshot.
            threshold: Override volume threshold.

        Returns:
            WallDetectionResult with bid and ask walls.
        """
        # Convert PriceLevel to dict for detect()
        bid_levels = [
            {"price": l.price, "volume": l.volume}
            for l in snapshot.bids[:self.depth_levels]
        ]
        ask_levels = [
            {"price": l.price, "volume": l.volume}
            for l in snapshot.asks[:self.depth_levels]
        ]

        bid_walls = self.detect(bid_levels, side=BookSide.BID, threshold=threshold)
        ask_walls = self.detect(ask_levels, side=BookSide.ASK, threshold=threshold)

        all_walls = bid_walls + ask_walls

        # Dominant side
        bid_strength = sum(w.strength_weight for w in bid_walls)
        ask_strength = sum(w.strength_weight for w in ask_walls)

        if bid_strength > ask_strength * 1.5:
            dominant = WallType.SUPPORT
        elif ask_strength > bid_strength * 1.5:
            dominant = WallType.RESISTANCE
        else:
            dominant = None

        # Wall imbalance: normalized bid vs ask wall strength
        total_strength = bid_strength + ask_strength
        wall_imbalance = (bid_strength - ask_strength) / max(total_strength, 1)

        # Price zone: price of strongest wall
        strongest = max(all_walls, key=lambda w: w.strength_weight) if all_walls else None
        price_zone = strongest.price if strongest else None

        result = WallDetectionResult(
            walls=all_walls,
            bid_walls=bid_walls,
            ask_walls=ask_walls,
            dominant_side=dominant,
            wall_imbalance=wall_imbalance,
            price_zone=price_zone,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_strength(self, volume: float, avg_volume: float) -> WallStrength:
        """Classify wall strength based on volume vs average.

        Args:
            volume: Wall volume.
            avg_volume: Average volume across levels.

        Returns:
            WallStrength classification.
        """
        if avg_volume == 0:
            return WallStrength.MINOR

        ratio = volume / avg_volume

        if ratio >= self.STRENGTH_MULTIPLIERS[WallStrength.FORTRESS]:
            return WallStrength.FORTRESS
        elif ratio >= self.STRENGTH_MULTIPLIERS[WallStrength.MAJOR]:
            return WallStrength.MAJOR
        elif ratio >= self.STRENGTH_MULTIPLIERS[WallStrength.MODERATE]:
            return WallStrength.MODERATE
        elif ratio >= self.STRENGTH_MULTIPLIERS[WallStrength.MINOR]:
            return WallStrength.MINOR
        else:
            return WallStrength.MINOR

    # ------------------------------------------------------------------
    # Wall Analysis
    # ------------------------------------------------------------------

    def predict_zone(
        self,
        result: Optional[WallDetectionResult] = None,
    ) -> dict[str, Any]:
        """Predict support/resistance zone from wall detection.

        Args:
            result: Specific result (default: latest).

        Returns:
            Dict with support_zone, resistance_zone, and confidence.
        """
        result = result or (self.history[-1] if self.history else None)
        if not result:
            return {"support_zone": None, "resistance_zone": None, "confidence": 0.0}

        support_zone = None
        support_conf = 0.0
        if result.bid_walls:
            strongest_bid = max(result.bid_walls, key=lambda w: w.strength_weight)
            support_zone = strongest_bid.price
            support_conf = min(1.0, strongest_bid.strength_weight / 4.0)

        resistance_zone = None
        resistance_conf = 0.0
        if result.ask_walls:
            strongest_ask = max(result.ask_walls, key=lambda w: w.strength_weight)
            resistance_zone = strongest_ask.price
            resistance_conf = min(1.0, strongest_ask.strength_weight / 4.0)

        return {
            "support_zone": support_zone,
            "support_confidence": round(support_conf, 4),
            "resistance_zone": resistance_zone,
            "resistance_confidence": round(resistance_conf, 4),
            "dominant_side": result.dominant_side.value if result.dominant_side else "none",
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_detect(
        self,
        levels: list[dict[str, Any]],
        side: BookSide = BookSide.BID,
    ) -> dict[str, Any]:
        """Quick wall detection returning summary dict.

        Args:
            levels: Price level dicts.
            side: BID or ASK.

        Returns:
            Dict with wall count and strongest wall info.
        """
        walls = self.detect(levels, side=side)
        strongest = walls[0] if walls else None
        return {
            "wall_count": len(walls),
            "strongest_wall": strongest.to_dict() if strongest else None,
            "significant_count": sum(1 for w in walls if w.is_significant),
        }

    def last_result(self) -> Optional[WallDetectionResult]:
        """Return the most recent detection result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset detection history."""
        self.history.clear()


# ---------------------------------------------------------------------------
# LiquidityWall.strength_weight property (defined outside for clarity)
# ---------------------------------------------------------------------------

def _strength_weight(self: LiquidityWall) -> float:
    """Numeric weight for strength comparison."""
    weights = {
        WallStrength.MINOR: 1,
        WallStrength.MODERATE: 2,
        WallStrength.MAJOR: 3,
        WallStrength.FORTRESS: 4,
    }
    return weights.get(self.strength, 1)


LiquidityWall.strength_weight = property(_strength_weight)
