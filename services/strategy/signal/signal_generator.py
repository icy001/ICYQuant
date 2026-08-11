"""
Signal Generator — Converts strategy context into standardized trading signals.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

This is the bridge between Strategy Platform (Part 1.1) and Signal Engine.
It consumes strategy runtime state and produces Signal objects.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import (
    Signal,
    SignalDirection,
    SignalStrength,
)

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trading signals from strategy context and alpha scores.

    This is where strategy-specific logic translates into the standard
    signal format. In production, this would be extended with pluggable
    generator strategies per signal source.
    """

    def __init__(self):
        self._generators: Dict[str, callable] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._register_builtin_generators()
        self._initialized = True
        logger.info("SignalGenerator initialized with %d generators", len(self._generators))

    async def shutdown(self) -> None:
        self._generators.clear()
        self._initialized = False

    def _register_builtin_generators(self) -> None:
        """Register default signal generation strategies."""
        self._generators["default"] = self._generate_default
        self._generators["alpha_driven"] = self._generate_alpha_driven
        self._generators["threshold"] = self._generate_threshold

    # ------------------------------------------------------------------
    # Main Interface
    # ------------------------------------------------------------------

    async def generate(
        self,
        strategy_id: str,
        instruments: List[str],
        context: Dict[str, Any],
        max_signals: int = 20,
        generator_type: str = "default",
    ) -> List[Signal]:
        """Generate signals from strategy context.

        Args:
            strategy_id: The originating strategy identifier.
            instruments: List of instruments to generate signals for.
            context: Strategy runtime context (alpha scores, factors, market data).
            max_signals: Maximum number of signals to return.
            generator_type: Which generator strategy to use.

        Returns:
            List of Signal objects ready for validation.
        """
        generator = self._generators.get(generator_type, self._generators["default"])
        signals = await generator(strategy_id, instruments, context)
        return signals[:max_signals]

    # ------------------------------------------------------------------
    # Generator Strategies
    # ------------------------------------------------------------------

    async def _generate_default(
        self,
        strategy_id: str,
        instruments: List[str],
        context: Dict[str, Any],
    ) -> List[Signal]:
        """Default generator: extracts signals from context['signals'] if present.

        Otherwise falls back to alpha-score-based generation.
        """
        # If context already contains pre-formed signals, use them
        raw_signals = context.get("signals", [])
        if raw_signals:
            signals = []
            for rs in raw_signals:
                if isinstance(rs, Signal):
                    signals.append(rs)
                elif isinstance(rs, dict):
                    signals.append(Signal(
                        strategy_id=strategy_id,
                        instrument=rs.get("instrument", ""),
                        direction=SignalDirection(rs.get("direction", "FLAT")),
                        strength=SignalStrength(rs.get("strength", "MODERATE")),
                        confidence=rs.get("confidence", 0.0),
                        reason=rs.get("reason", ""),
                        alpha_scores=rs.get("alpha_scores", {}),
                        factor_contributions=rs.get("factor_contributions", {}),
                        tags=rs.get("tags", []),
                        metadata=rs.get("metadata", {}),
                    ))
            return signals

        # Fallback: derive from alpha scores
        return await self._generate_alpha_driven(strategy_id, instruments, context)

    async def _generate_alpha_driven(
        self,
        strategy_id: str,
        instruments: List[str],
        context: Dict[str, Any],
    ) -> List[Signal]:
        """Generate signals from alpha scores in context.

        Uses combined_alpha scores per instrument to determine direction and strength.
        """
        alphas = context.get("alphas", {})
        combined = context.get("combined_alpha", {})
        signals = []

        for inst in instruments:
            score = combined.get(inst, 0.0)

            if abs(score) < 0.01:
                continue

            direction = SignalDirection.LONG if score > 0 else SignalDirection.SHORT
            abs_score = abs(score)

            if abs_score > 0.8:
                strength = SignalStrength.VERY_STRONG
            elif abs_score > 0.5:
                strength = SignalStrength.STRONG
            elif abs_score > 0.2:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            signals.append(Signal(
                strategy_id=strategy_id,
                instrument=inst,
                direction=direction,
                strength=strength,
                confidence=min(abs_score, 1.0),
                reason=f"Alpha score: {score:.4f}",
                alpha_scores=alphas.get(inst, {}),
            ))

        return signals

    async def _generate_threshold(
        self,
        strategy_id: str,
        instruments: List[str],
        context: Dict[str, Any],
    ) -> List[Signal]:
        """Generate signals based on threshold crossings from context."""
        thresholds = context.get("thresholds", {})
        values = context.get("values", {})
        signals = []

        for inst in instruments:
            val = values.get(inst)
            if val is None:
                continue

            long_threshold = thresholds.get("long", 0.7)
            short_threshold = thresholds.get("short", -0.7)

            if val > long_threshold:
                signals.append(Signal(
                    strategy_id=strategy_id,
                    instrument=inst,
                    direction=SignalDirection.LONG,
                    strength=SignalStrength.STRONG if val > long_threshold + 0.1 else SignalStrength.MODERATE,
                    confidence=min(val, 1.0),
                    reason=f"Value {val:.4f} above long threshold {long_threshold}",
                ))
            elif val < short_threshold:
                signals.append(Signal(
                    strategy_id=strategy_id,
                    instrument=inst,
                    direction=SignalDirection.SHORT,
                    strength=SignalStrength.STRONG if val < short_threshold - 0.1 else SignalStrength.MODERATE,
                    confidence=min(abs(val), 1.0),
                    reason=f"Value {val:.4f} below short threshold {short_threshold}",
                ))

        return signals

    # ------------------------------------------------------------------
    # Extensibility
    # ------------------------------------------------------------------

    def register_generator(self, name: str, generator: callable) -> None:
        """Register a custom signal generator strategy."""
        self._generators[name] = generator
        logger.info("Registered signal generator: %s", name)
