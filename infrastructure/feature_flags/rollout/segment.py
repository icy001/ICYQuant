"""
Segment-based rollout engine.

Enables targeting specific groups of targets
based on attribute matching (broker, account type,
strategy group, etc.) combined with percentage
based rollout within each segment.

Segments are evaluated in priority order.
The first matching segment determines the
rollout percentage override.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rollout import SegmentDefinition


class SegmentEngine:
    """
    Segment-based rollout engine.

    Manages a set of segment definitions and
    resolves which segment (if any) a target
    belongs to based on its attributes.

    Segments can override the default rollout
    percentage, enabling targeted rollout within
    specific groups.

    Usage:
        engine = SegmentEngine()
        engine.add_segment(SegmentDefinition(
            segment_id="vip",
            attribute="account_type",
            operator="==",
            values=["vip"],
            percentage=50.0,
        ))
        segment = engine.resolve({"account_type": "vip", "broker": "IBKR"})
        # segment.percentage == 50.0
    """

    def __init__(self) -> None:
        """Initialize the segment engine."""
        self._segments: List[SegmentDefinition] = []
        self._segment_map: Dict[str, SegmentDefinition] = {}

    def add_segment(self, segment: SegmentDefinition) -> None:
        """
        Add a segment definition.

        Args:
            segment: Segment to add.
        """
        self._segments.append(segment)
        self._segments.sort(key=lambda s: s.priority)
        self._segment_map[segment.segment_id] = segment

    def remove_segment(self, segment_id: str) -> bool:
        """
        Remove a segment by ID.

        Args:
            segment_id: Segment to remove.

        Returns:
            True if removed.
        """
        if segment_id in self._segment_map:
            segment = self._segment_map.pop(segment_id)
            self._segments.remove(segment)
            return True
        return False

    def resolve(
        self,
        attributes: Dict[str, Any],
    ) -> Optional[SegmentDefinition]:
        """
        Resolve which segment matches the given attributes.

        Evaluates segments in priority order and returns
        the first matching segment. Segments with
        percentage override are included.

        Args:
            attributes: Target attributes to match against.

        Returns:
            Matching SegmentDefinition or None.
        """
        for segment in self._segments:
            if not segment.enabled:
                continue
            if segment.matches(attributes):
                return segment
        return None

    def resolve_all(
        self,
        attributes: Dict[str, Any],
    ) -> List[SegmentDefinition]:
        """
        Resolve all matching segments.

        Args:
            attributes: Target attributes.

        Returns:
            List of matching segments.
        """
        return [
            s for s in self._segments
            if s.enabled and s.matches(attributes)
        ]

    def get_segment(self, segment_id: str) -> Optional[SegmentDefinition]:
        """
        Get a segment by ID.

        Args:
            segment_id: Segment ID.

        Returns:
            SegmentDefinition or None.
        """
        return self._segment_map.get(segment_id)

    def get_segments(self) -> List[SegmentDefinition]:
        """Get all segments sorted by priority."""
        return list(self._segments)

    def clear(self) -> None:
        """Remove all segments."""
        self._segments.clear()
        self._segment_map.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get segment engine statistics."""
        return {
            "total_segments": len(self._segments),
            "active_segments": sum(1 for s in self._segments if s.enabled),
            "by_attribute": self._group_by_attribute(),
        }

    def _group_by_attribute(self) -> Dict[str, int]:
        """Group segments by attribute."""
        counts: Dict[str, int] = {}
        for s in self._segments:
            counts[s.attribute] = counts.get(s.attribute, 0) + 1
        return counts
