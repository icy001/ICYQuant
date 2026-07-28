"""Capital Rotation Engine.

Detects capital rotation between sectors, asset classes, and regions
by analyzing flow patterns and identifying migration trends for
positioning and alpha generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import CapitalFlowRecord, SectorRotation


@dataclass
class RotationResult:
    """Result of capital rotation analysis.

    Attributes:
        rotations: Detected sector/asset rotations.
        has_rotation: Whether any rotation was detected.
        summary: Human-readable summary.
        rotation_map: Map of flow changes between sectors.
        timestamp: Detection timestamp.
    """

    rotations: list[SectorRotation] = field(default_factory=list)
    has_rotation: bool = False
    summary: str = ""
    rotation_map: dict[str, dict[str, float]] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def count(self) -> int:
        return len(self.rotations)

    @property
    def significant_count(self) -> int:
        return sum(1 for r in self.rotations if r.is_significant)


class CapitalRotationEngine:
    """Detects and analyzes capital rotation patterns.

    Identifies capital migration between sectors, assets, and regions
    by comparing flow strength and direction across groups.

    Attributes:
    detected_rotations: History of all detected rotations.
        min_flow_threshold: Minimum absolute flow to signal rotation.
    """

    def __init__(self) -> None:
        self.detected_rotations: list[SectorRotation] = []
        self.min_flow_threshold: float = 0.3

    # --- Detection ---

    def detect(
        self,
        sectors: dict[str, list[CapitalFlowRecord]] | None = None,
    ) -> dict[str, Any]:
        """Detect capital rotation from sector flow data.

        Args:
            sectors: Dict mapping sector names to their flow records.

        Returns:
            Dict with rotation analysis.
        """
        if not sectors:
            return {"rotation": {}, "has_rotation": False}

        result = self.analyze(sectors)
        return {
            "rotation": {r.name: r.description for r in result.rotations} if result.rotations else {},
            "has_rotation": result.has_rotation,
            "summary": result.summary,
        }

    def analyze(
        self,
        sectors: dict[str, list[CapitalFlowRecord]] | None = None,
    ) -> RotationResult:
        """Full rotation analysis.

        Args:
            sectors: Dict mapping sector names to their flow records.

        Returns:
            RotationResult with detected rotations.
        """
        if not sectors:
            return RotationResult(summary="No sector data for rotation analysis.")

        # Compute net flow per sector
        sector_flows: dict[str, float] = {}
        for sector, flows in sectors.items():
            net = sum(f.net_flow_value for f in flows) if flows else 0.0
            sector_flows[sector] = net

        # Build rotation map
        rotation_map: dict[str, dict[str, float]] = {}
        for from_sector, from_flow in sector_flows.items():
            if from_flow >= -self.min_flow_threshold:
                continue
            for to_sector, to_flow in sector_flows.items():
                if to_flow <= self.min_flow_threshold:
                    continue
                if from_sector != to_sector:
                    strength = min(abs(from_flow), abs(to_flow))
                    rotation_map.setdefault(from_sector, {})[to_sector] = strength

        # Create rotation objects
        rotations: list[SectorRotation] = []
        for from_s, targets in rotation_map.items():
            for to_s, strength in sorted(targets.items(), key=lambda x: -x[1]):
                name = f"{from_s}_to_{to_s}"
                rot = SectorRotation(
                    name=name,
                    source_sectors=[from_s],
                    target_sectors=[to_s],
                    strength=min(1.0, strength / 5.0),
                    confidence=min(1.0, 0.5 + strength / 10.0),
                    flow_amount=sector_flows[to_s] - sector_flows[from_s],
                    description=f"Capital rotating from {from_s} to {to_s} (strength={strength:.2f})",
                )
                rotations.append(rot)

        self.detected_rotations.extend(rotations)

        summary = self._summarize(rotations, sector_flows)
        return RotationResult(
            rotations=rotations,
            has_rotation=len(rotations) > 0,
            summary=summary,
            rotation_map=rotation_map,
        )

    # --- Analysis Helpers ---

    def get_sector_momentum(self, sector: str) -> float:
        """Get accumulated rotation momentum for a sector.

        Args:
            sector: Sector name.

        Returns:
            Net rotation momentum (positive = rotating into).
        """
        net = 0.0
        for rotation in self.detected_rotations:
            if sector in rotation.source_sectors:
                net -= rotation.strength
            if sector in rotation.target_sectors:
                net += rotation.strength
        return net

    def get_hottest_sectors(self, limit: int = 3) -> list[tuple[str, float]]:
        """Get sectors with most capital inflows.

        Args:
            limit: Maximum number to return.

        Returns:
            List of (sector, momentum) tuples sorted by momentum descending.
        """
        sectors: set[str] = set()
        for r in self.detected_rotations:
            sectors.update(r.source_sectors)
            sectors.update(r.target_sectors)

        momentum = [(s, self.get_sector_momentum(s)) for s in sectors]
        return sorted(momentum, key=lambda x: -x[1])[:limit]

    def get_coldest_sectors(self, limit: int = 3) -> list[tuple[str, float]]:
        """Get sectors with most capital outflows.

        Args:
            limit: Maximum number to return.

        Returns:
            List of (sector, momentum) tuples sorted by momentum ascending.
        """
        sectors: set[str] = set()
        for r in self.detected_rotations:
            sectors.update(r.source_sectors)
            sectors.update(r.target_sectors)

        momentum = [(s, self.get_sector_momentum(s)) for s in sectors]
        return sorted(momentum, key=lambda x: x[1])[:limit]

    # --- Internal ---

    def _summarize(
        self,
        rotations: list[SectorRotation],
        sector_flows: dict[str, float],
    ) -> str:
        """Generate analysis summary."""
        if not rotations:
            return "No significant capital rotation detected."

        parts: list[str] = []
        top = sorted(rotations, key=lambda r: -r.strength)[:3]
        for r in top:
            parts.append(
                f"{r.source_sectors[0]} → {r.target_sectors[0]} "
                f"(strength={r.strength:.2f})"
            )
        return "Rotation detected: " + " | ".join(parts)

    def clear(self) -> None:
        """Reset engine state."""
        self.detected_rotations.clear()
