"""
Signal Normalizer — Semantic unification of signal fields across different sources.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Unifies variant semantics into canonical forms:
    BUY, LONG, OPEN_LONG  →  LONG
    SELL, SHORT, OPEN_SHORT  →  SHORT
    CLOSE, EXIT, FLATTEN  →  FLAT
"""

from __future__ import annotations

import logging
from typing import Dict

from services.strategy.signal.signal_engine import Signal, SignalDirection, SignalStrength

logger = logging.getLogger(__name__)


class SignalNormalizer:
    """Normalizes signal semantics to ensure all signals use canonical values.

    Different strategies and alpha models may use different terminology.
    This normalizer maps all variants to a unified set of enums.
    """

    # ------------------------------------------------------------------
    # Canonical Mappings
    # ------------------------------------------------------------------

    DIRECTION_MAP: Dict[str, SignalDirection] = {
        # Long variants
        "BUY": SignalDirection.LONG,
        "LONG": SignalDirection.LONG,
        "OPEN_LONG": SignalDirection.LONG,
        "ENTER_LONG": SignalDirection.LONG,
        "GO_LONG": SignalDirection.LONG,
        "B": SignalDirection.LONG,
        "1": SignalDirection.LONG,
        # Short variants
        "SELL": SignalDirection.SHORT,
        "SHORT": SignalDirection.SHORT,
        "OPEN_SHORT": SignalDirection.SHORT,
        "ENTER_SHORT": SignalDirection.SHORT,
        "GO_SHORT": SignalDirection.SHORT,
        "S": SignalDirection.SHORT,
        "-1": SignalDirection.SHORT,
        # Flat variants
        "CLOSE": SignalDirection.FLAT,
        "EXIT": SignalDirection.FLAT,
        "FLAT": SignalDirection.FLAT,
        "FLATTEN": SignalDirection.FLAT,
        "NEUTRAL": SignalDirection.FLAT,
        "HOLD": SignalDirection.FLAT,
        "0": SignalDirection.FLAT,
    }

    STRENGTH_MAP: Dict[str, SignalStrength] = {
        "WEAK": SignalStrength.WEAK,
        "LOW": SignalStrength.WEAK,
        "1": SignalStrength.WEAK,
        "MODERATE": SignalStrength.MODERATE,
        "MEDIUM": SignalStrength.MODERATE,
        "MID": SignalStrength.MODERATE,
        "2": SignalStrength.MODERATE,
        "STRONG": SignalStrength.STRONG,
        "HIGH": SignalStrength.STRONG,
        "3": SignalStrength.STRONG,
        "VERY_STRONG": SignalStrength.VERY_STRONG,
        "EXTREME": SignalStrength.VERY_STRONG,
        "4": SignalStrength.VERY_STRONG,
    }

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    async def normalize_direction(self, signal: Signal) -> SignalDirection:
        """Normalize the signal direction to canonical form.

        If the signal already has a valid SignalDirection enum, returns it directly.
        Otherwise, attempts to map from string variants in metadata.
        """
        # Already canonical
        if isinstance(signal.direction, SignalDirection):
            return signal.direction

        # Try to map from string
        if isinstance(signal.direction, str):
            upper = signal.direction.upper().strip()
            canonical = self.DIRECTION_MAP.get(upper)
            if canonical:
                return canonical
            # Try numeric
            try:
                val = float(upper)
                if val > 0:
                    return SignalDirection.LONG
                elif val < 0:
                    return SignalDirection.SHORT
                else:
                    return SignalDirection.FLAT
            except ValueError:
                pass

        # Check metadata for direction hints
        meta_dir = signal.metadata.get("direction", signal.metadata.get("side", ""))
        if isinstance(meta_dir, str):
            upper = meta_dir.upper().strip()
            canonical = self.DIRECTION_MAP.get(upper)
            if canonical:
                return canonical

        logger.warning("Unknown direction '%s' for signal %s, defaulting to FLAT",
                       signal.direction, signal.signal_id)
        return SignalDirection.FLAT

    async def normalize_strength(self, signal: Signal) -> SignalStrength:
        """Normalize the signal strength to canonical form."""
        if isinstance(signal.strength, SignalStrength):
            return signal.strength

        if isinstance(signal.strength, str):
            upper = signal.strength.upper().strip()
            canonical = self.STRENGTH_MAP.get(upper)
            if canonical:
                return canonical

        # Derive from confidence
        if signal.confidence > 0.8:
            return SignalStrength.VERY_STRONG
        elif signal.confidence > 0.5:
            return SignalStrength.STRONG
        elif signal.confidence > 0.2:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    async def normalize(self, signal: Signal) -> Signal:
        """Full normalization: direction + strength."""
        signal.direction = await self.normalize_direction(signal)
        signal.strength = await self.normalize_strength(signal)
        return signal
