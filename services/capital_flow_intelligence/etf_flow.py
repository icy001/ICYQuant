"""ETF Flow Intelligence.

Analyzes ETF capital flows to detect sector rotation, thematic trends,
and institutional positioning through ETF vehicles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import CapitalFlowRecord, FlowSource, FlowDirection


# Sector ETF mapping for classification
SECTOR_ETF_MAP: dict[str, str] = {
    # Technology / Semiconductor
    "SOXL": "semiconductor", "SOXS": "semiconductor",
    "SMH": "semiconductor", "SOXX": "semiconductor",
    "XLK": "technology", "QQQ": "technology",
    "VGT": "technology", "TECL": "technology",
    # Financial
    "XLF": "financial", "FAS": "financial", "FAZ": "financial",
    "VFH": "financial",
    # Healthcare
    "XLV": "healthcare", "CURE": "healthcare",
    "VHT": "healthcare", "IBB": "biotech",
    # Energy
    "XLE": "energy", "ERX": "energy", "ERY": "energy",
    "VDE": "energy", "XOP": "energy",
    # Consumer
    "XLY": "consumer", "XLP": "consumer_staples",
    "VDC": "consumer_staples", "XRT": "retail",
    # Industrial
    "XLI": "industrial", "VIS": "industrial",
    # Real Estate
    "XLRE": "real_estate", "VNQ": "real_estate",
    # Utilities
    "XLU": "utilities", "VPU": "utilities",
    # Materials
    "XLB": "materials", "VAW": "materials",
    # Broad Market
    "SPY": "broad_market", "IVV": "broad_market",
    "VTI": "broad_market", "IWM": "small_cap",
    "DIA": "broad_market",
    # Bonds
    "TLT": "treasury_long", "SHY": "treasury_short",
    "LQD": "corporate_bond", "HYG": "high_yield",
    "AGG": "aggregate_bond", "BND": "aggregate_bond",
    # Commodities
    "GLD": "gold", "IAU": "gold", "SLV": "silver",
    "USO": "oil", "UNG": "natural_gas",
    # Currency
    "UUP": "dollar", "FXE": "euro",
}


@dataclass
class ETFFlowResult:
    """Result of ETF flow analysis.

    Attributes:
        etf: ETF ticker analyzed.
        sector: Mapped sector classification.
        flow_direction: Net flow direction.
        flow_score: Normalized flow score [-1.0, 1.0].
        streak: Consecutive periods of same direction.
        confidence: Analysis confidence [0.0, 1.0].
        description: Human-readable summary.
        sector_rotation_signal: Whether this signals sector rotation.
        timestamp: Analysis timestamp.
    """

    etf: str = ""
    sector: str = "unknown"
    flow_direction: str = "neutral"
    flow_score: float = 0.0
    streak: int = 0
    confidence: float = 0.5
    description: str = ""
    sector_rotation_signal: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_positive_flow(self) -> bool:
        return self.flow_direction == "positive"

    @property
    def is_negative_flow(self) -> bool:
        return self.flow_direction == "negative"

    @property
    def is_strong_signal(self) -> bool:
        return abs(self.flow_score) >= 0.7 and self.streak >= 5


class ETFFlowAnalyzer:
    """Analyzes ETF capital flows for sector rotation signals.

    Tracks ETF inflows/outflows to detect thematic positioning,
    sector rotation, and institutional flows through ETF vehicles.

    Attributes:
        sector_map: Mapping of ETF tickers to sector classifications.
        flow_history: Per-etf flow history.
        streak_threshold: Consecutive periods to signal trend.
    """

    def __init__(self) -> None:
        self.sector_map: dict[str, str] = dict(SECTOR_ETF_MAP)
        self.flow_history: dict[str, list[float]] = {}
        self.streak_threshold: int = 5

    # --- Analysis ---

    def analyze(self, etf: str, flows: list[CapitalFlowRecord] | None = None) -> dict[str, Any]:
        """Analyze ETF flow for a given ticker.

        Args:
            etf: ETF ticker symbol.
            flows: Optional list of flow records (filtered to this ETF).

        Returns:
            Dict with flow analysis result.
        """
        sector = self._classify_sector(etf)
        score = self._compute_flow_score(flows) if flows else 0.0
        streak = self._compute_streak(etf, score)
        direction = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"

        return {
            "etf": etf,
            "sector": sector,
            "flow": direction,
            "flow_score": score,
            "streak": streak,
            "sector_rotation_signal": abs(score) >= 0.5 and streak >= self.streak_threshold,
        }

    def analyze_full(self, etf: str, flows: list[CapitalFlowRecord] | None = None) -> ETFFlowResult:
        """Full ETF flow analysis with detailed result.

        Args:
            etf: ETF ticker symbol.
            flows: Optional flow records.

        Returns:
            ETFFlowResult with detailed analysis.
        """
        sector = self._classify_sector(etf)
        score = self._compute_flow_score(flows) if flows else 0.0
        streak = self._compute_streak(etf, score)
        direction = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"

        confidence = self._compute_confidence(flows, streak) if flows else 0.3
        rotation_signal = abs(score) >= 0.5 and streak >= self.streak_threshold

        description = self._generate_description(etf, sector, direction, score, streak)

        return ETFFlowResult(
            etf=etf,
            sector=sector,
            flow_direction=direction,
            flow_score=score,
            streak=streak,
            confidence=confidence,
            description=description,
            sector_rotation_signal=rotation_signal,
        )

    def analyze_sector(self, sector: str, etf_flows: dict[str, list[CapitalFlowRecord]]) -> ETFFlowResult:
        """Analyze aggregate flow for a sector.

        Args:
            sector: Sector name.
            etf_flows: Dict mapping ETF tickers to their flow records.

        Returns:
            ETFFlowResult for the sector.
        """
        sector_etfs = [e for e, s in self.sector_map.items() if s == sector]
        all_flows: list[CapitalFlowRecord] = []
        for etf in sector_etfs:
            flows = etf_flows.get(etf, [])
            all_flows.extend(flows)

        score = self._compute_flow_score(all_flows) if all_flows else 0.0
        direction = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"

        return ETFFlowResult(
            etf=f"sector:{sector}",
            sector=sector,
            flow_direction=direction,
            flow_score=score,
            confidence=0.6 if all_flows else 0.3,
            description=f"Sector {sector}: {direction} flow (score={score:.2f})",
        )

    def get_sector_flow_map(
        self, etf_flows: dict[str, list[CapitalFlowRecord]]
    ) -> dict[str, float]:
        """Get aggregated flow scores per sector.

        Args:
            etf_flows: Dict mapping ETF tickers to their flow records.

        Returns:
            Dict mapping sector name to flow score.
        """
        sector_scores: dict[str, list[float]] = {}
        for etf, flows in etf_flows.items():
            sector = self._classify_sector(etf)
            score = self._compute_flow_score(flows)
            sector_scores.setdefault(sector, []).append(score)

        return {s: sum(scores) / len(scores) for s, scores in sector_scores.items()}

    # --- Classification ---

    def classify_etf(self, etf: str) -> str:
        """Classify an ETF into a sector.

        Args:
            etf: ETF ticker.

        Returns:
            Sector classification string.
        """
        return self._classify_sector(etf)

    def add_etf_mapping(self, etf: str, sector: str) -> None:
        """Add a custom ETF-to-sector mapping.

        Args:
            etf: ETF ticker.
            sector: Sector classification.
        """
        self.sector_map[etf.upper()] = sector.lower()

    # --- Sector Rotation ---

    def detect_rotation(
        self, etf_flows: dict[str, list[CapitalFlowRecord]]
    ) -> list[dict[str, Any]]:
        """Detect potential sector rotations from ETF flows.

        Args:
            etf_flows: Dict mapping ETF tickers to flow records.

        Returns:
            List of rotation signals.
        """
        sector_map = self.get_sector_flow_map(etf_flows)
        if not sector_map:
            return []

        # Find sectors with strong positive and negative flows
        inflows = [(s, v) for s, v in sector_map.items() if v > 0.3]
        outflows = [(s, v) for s, v in sector_map.items() if v < -0.3]

        rotations: list[dict[str, Any]] = []
        for out_sector, out_score in outflows:
            for in_sector, in_score in inflows:
                strength = min(abs(out_score), abs(in_score))
                rotations.append({
                    "from_sector": out_sector,
                    "to_sector": in_sector,
                    "outflow_score": out_score,
                    "inflow_score": in_score,
                    "strength": strength,
                })

        return sorted(rotations, key=lambda x: x["strength"], reverse=True)

    # --- Internal ---

    def _classify_sector(self, etf: str) -> str:
        """Classify an ETF ticker to its sector."""
        return self.sector_map.get(etf.upper(), "unknown")

    def _compute_flow_score(self, flows: list[CapitalFlowRecord]) -> float:
        """Compute normalized flow score from records.

        Args:
            flows: List of flow records.

        Returns:
            Normalized score [-1.0, 1.0].
        """
        if not flows:
            return 0.0

        net = sum(f.net_flow_value for f in flows)
        total = sum(abs(f.amount) for f in flows)
        if total == 0:
            return 0.0
        return max(-1.0, min(1.0, net / total * 2.0))

    def _compute_streak(self, etf: str, current_score: float) -> int:
        """Compute consecutive periods of same flow direction.

        Args:
            etf: ETF ticker.
            current_score: Current flow score.

        Returns:
            Streak count.
        """
        history = self.flow_history.setdefault(etf, [])
        history.append(current_score)

        is_positive = current_score > 0

        streak = 0
        for score in reversed(history):
            if (is_positive and score > 0) or (not is_positive and score < 0):
                streak += 1
            else:
                break
        return streak

    def _compute_confidence(
        self, flows: list[CapitalFlowRecord], streak: int
    ) -> float:
        """Compute analysis confidence.

        Args:
            flows: Flow records.
            streak: Consecutive direction streak.

        Returns:
            Confidence [0.0, 1.0].
        """
        confidence = 0.3

        if len(flows) >= 10:
            confidence += 0.2
        elif len(flows) >= 5:
            confidence += 0.1

        if streak >= self.streak_threshold:
            confidence += 0.3
        elif streak >= 3:
            confidence += 0.15

        return min(1.0, confidence)

    def _generate_description(
        self, etf: str, sector: str, direction: str, score: float, streak: int
    ) -> str:
        """Generate human-readable description."""
        if direction == "neutral":
            return f"{etf} ({sector}): flow neutral (score={score:.2f})"

        dur = f"for {streak} periods" if streak >= 3 else ""
        flow_word = "inflow" if direction == "positive" else "outflow"
        parts = [f"{etf} ({sector}): {flow_word}" + (f" {dur}" if dur else "")]
        parts.append(f"(score={score:.2f})")

        if abs(score) >= 0.5 and streak >= self.streak_threshold:
            parts.append("[ROTATION SIGNAL]")

        return " ".join(parts)

    def clear(self) -> None:
        """Reset analyzer state."""
        self.flow_history.clear()
