"""Investor Emotion Detector.

Detects market emotion states by analyzing sentiment patterns and identifying
crowd psychology phases: Euphoria, Optimism, Neutral, Fear, Panic, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import EmotionState, SentimentRecord, SentimentLabel


@dataclass
class EmotionResult:
    """Result of emotion detection analysis.

    Attributes:
        state: Detected emotion state.
        score: Composite emotion score [0, 100] (higher = more positive emotion).
        intensity: Emotion intensity [0.0, 1.0].
        confidence: Detection confidence [0.0, 1.0].
        signals: Contributing signals summary.
        timestamp: Detection timestamp.
        transition: Whether a state transition was detected.
        previous_state: Previous emotion state if transition detected.
        description: Human-readable description.
    """

    state: EmotionState = EmotionState.NEUTRAL
    score: float = 50.0
    intensity: float = 0.5
    confidence: float = 0.5
    signals: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    transition: bool = False
    previous_state: EmotionState | None = None
    description: str = ""

    @property
    def is_extreme(self) -> bool:
        return self.state in (
            EmotionState.EUPHORIA,
            EmotionState.PANIC,
            EmotionState.CAPITULATION,
            EmotionState.DESPAIR,
        )

    @property
    def is_positive(self) -> bool:
        return self.state in (
            EmotionState.EUPHORIA,
            EmotionState.OPTIMISM,
            EmotionState.HOPE,
            EmotionState.RELIEF,
        )

    @property
    def is_negative(self) -> bool:
        return self.state in (
            EmotionState.ANXIETY,
            EmotionState.FEAR,
            EmotionState.PANIC,
            EmotionState.CAPITULATION,
            EmotionState.DESPAIR,
        )


class EmotionDetector:
    """Detects investor emotion states from sentiment data.

    Maps sentiment scores and patterns to market psychology states
    including Euphoria, Optimism, Fear, Panic, and Capitulation.

    Attributes:
        current_state: Current detected emotion state.
        state_history: History of state transitions.
        score_history: Rolling history of sentiment scores.
        threshold_euphoria: Score threshold for euphoria detection.
        threshold_optimism: Score threshold for optimism.
        threshold_fear: Score threshold for fear.
        threshold_panic: Score threshold for panic.
    """

    def __init__(self) -> None:
        self.current_state: EmotionState = EmotionState.NEUTRAL
        self.state_history: list[EmotionState] = []
        self.score_history: list[float] = []

        # Configurable thresholds
        self.threshold_euphoria: float = 85.0
        self.threshold_optimism: float = 65.0
        self.threshold_hope: float = 55.0
        self.threshold_anxiety: float = 45.0
        self.threshold_fear: float = 35.0
        self.threshold_panic: float = 20.0
        self.threshold_capitulation: float = 15.0
        self.threshold_despair: float = 10.0

    # --- Detection ---

    def detect(self, score: float) -> EmotionState:
        """Detect emotion state from a sentiment score.

        Args:
            score: Sentiment score [0, 100] where 50 is neutral.

        Returns:
            Detected EmotionState.
        """
        if score > self.threshold_euphoria:
            return EmotionState.EUPHORIA
        elif score > self.threshold_optimism:
            return EmotionState.OPTIMISM
        elif score > self.threshold_hope:
            return EmotionState.HOPE
        elif score > self.threshold_anxiety:
            return EmotionState.NEUTRAL
        elif score > self.threshold_fear:
            return EmotionState.ANXIETY
        elif score > self.threshold_panic:
            return EmotionState.FEAR
        elif score > self.threshold_capitulation:
            return EmotionState.PANIC
        elif score > self.threshold_despair:
            return EmotionState.CAPITULATION
        else:
            return EmotionState.DESPAIR

    def analyze(self, sentiment_score: float, additional_signals: dict[str, float] | None = None) -> EmotionResult:
        """Full emotion analysis with state tracking and transition detection.

        Args:
            sentiment_score: Aggregate sentiment score [0, 100].
            additional_signals: Optional additional signal values (put/call, vol, etc.).

        Returns:
            EmotionResult with state, intensity, and transition info.
        """
        new_state = self.detect(sentiment_score)
        previous_state = self.current_state

        # Track history
        self.score_history.append(sentiment_score)
        if len(self.score_history) > 100:
            self.score_history = self.score_history[-100:]

        # Detect transition
        transition = new_state != self.current_state
        if transition:
            self.state_history.append(self.current_state)

        self.current_state = new_state

        # Compute intensity
        intensity = self._compute_intensity(sentiment_score, new_state)

        # Compute confidence
        confidence = self._compute_confidence(sentiment_score, new_state, additional_signals or {})

        # Build description
        description = self._describe_state(new_state, sentiment_score, transition, previous_state)

        return EmotionResult(
            state=new_state,
            score=sentiment_score,
            intensity=intensity,
            confidence=confidence,
            signals=additional_signals or {},
            transition=transition,
            previous_state=previous_state if transition else None,
            description=description,
        )

    def analyze_records(self, records: list[SentimentRecord]) -> EmotionResult:
        """Analyze emotion from a batch of sentiment records.

        Args:
            records: List of SentimentRecords.

        Returns:
            EmotionResult.
        """
        if not records:
            return EmotionResult(description="No records to analyze.")

        # Compute weighted average score
        total_weight = 0.0
        weighted_score = 0.0
        for r in records:
            weight = r.confidence
            # Map [-1, 1] to [0, 100]
            normalized_score = (r.score + 1.0) / 2.0 * 100.0
            weighted_score += normalized_score * weight
            total_weight += weight

        if total_weight == 0:
            avg_score = 50.0
        else:
            avg_score = weighted_score / total_weight

        # Collect additional signals
        signals: dict[str, float] = {
            "record_count": float(len(records)),
            "positive_ratio": sum(1 for r in records if r.is_positive) / len(records) if records else 0.0,
            "negative_ratio": sum(1 for r in records if r.is_negative) / len(records) if records else 0.0,
            "extreme_ratio": sum(1 for r in records if r.is_extreme) / len(records) if records else 0.0,
            "avg_confidence": sum(r.confidence for r in records) / len(records) if records else 0.0,
        }

        return self.analyze(avg_score, signals)

    def analyze_score(self, score: float) -> EmotionState:
        """Simple score-to-emotion mapping (convenience method).

        Args:
            score: Sentiment score [-1.0, 1.0] or [0, 100].

        Returns:
            Detected EmotionState.
        """
        if -1.0 <= score <= 1.0:
            score = (score + 1.0) / 2.0 * 100.0
        return self.detect(score)

    # --- Analysis Helpers ---

    def get_sentiment_trend(self, window: int = 10) -> str:
        """Get recent sentiment trend direction.

        Args:
            window: Number of recent scores to analyze.

        Returns:
            Trend description: 'rising', 'falling', or 'stable'.
        """
        if len(self.score_history) < 2:
            return "stable"

        recent = self.score_history[-window:]
        if len(recent) < 2:
            return "stable"

        first_half = sum(recent[: len(recent) // 2]) / (len(recent) // 2)
        second_half = sum(recent[len(recent) // 2 :]) / (len(recent) - len(recent) // 2)

        diff = second_half - first_half
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        return "stable"

    def get_extreme_risk(self) -> float:
        """Compute extreme emotion risk level [0.0, 1.0].

        Returns:
            Risk level where high values indicate extreme emotional states.
        """
        if self.current_state in (EmotionState.EUPHORIA,):
            return 0.8  # Euphoria risk: potential bubble
        elif self.current_state in (EmotionState.PANIC,):
            return 0.9  # Panic risk: capitulation selling
        elif self.current_state in (EmotionState.CAPITULATION, EmotionState.DESPAIR):
            return 1.0  # Maximum risk
        elif self.current_state in (EmotionState.OPTIMISM, EmotionState.HOPE, EmotionState.RELIEF):
            return 0.2  # Low risk
        elif self.current_state in (EmotionState.FEAR, EmotionState.ANXIETY):
            return 0.6  # Moderate risk
        return 0.3  # Neutral

    # --- Internal Methods ---

    def _compute_intensity(self, score: float, state: EmotionState) -> float:
        """Compute how intense the current emotion state is.

        Args:
            score: Sentiment score.
            state: Current emotion state.

        Returns:
            Intensity [0.0, 1.0].
        """
        if state == EmotionState.EUPHORIA:
            return min(1.0, (score - self.threshold_euphoria) / (100.0 - self.threshold_euphoria))
        elif state == EmotionState.OPTIMISM:
            return (score - self.threshold_optimism) / (self.threshold_euphoria - self.threshold_optimism)
        elif state == EmotionState.HOPE:
            return (score - self.threshold_hope) / (self.threshold_optimism - self.threshold_hope)
        elif state == EmotionState.NEUTRAL:
            return 1.0 - abs(score - 50.0) / 5.0
        elif state == EmotionState.ANXIETY:
            return (self.threshold_anxiety - score) / (self.threshold_anxiety - self.threshold_fear)
        elif state == EmotionState.FEAR:
            return (self.threshold_fear - score) / (self.threshold_fear - self.threshold_panic)
        elif state == EmotionState.PANIC:
            return (self.threshold_panic - score) / (self.threshold_panic - self.threshold_capitulation)
        elif state == EmotionState.CAPITULATION:
            return (self.threshold_capitulation - score) / (self.threshold_capitulation - self.threshold_despair)
        else:  # DESPAIR
            return 1.0

    def _compute_confidence(
        self,
        score: float,
        state: EmotionState,
        signals: dict[str, float],
    ) -> float:
        """Compute detection confidence.

        Args:
            score: Sentiment score.
            state: Detected state.
            signals: Additional signal values.

        Returns:
            Confidence [0.0, 1.0].
        """
        base_confidence = 0.5

        # More extreme scores = higher confidence
        distance_from_neutral = abs(score - 50.0) / 50.0
        base_confidence += 0.3 * distance_from_neutral

        # Additional signals increase confidence
        if signals:
            base_confidence += 0.1 * min(1.0, len(signals) / 5.0)

        # History length increases confidence
        if len(self.score_history) > 10:
            base_confidence += 0.1

        return min(1.0, base_confidence)

    def _describe_state(
        self,
        state: EmotionState,
        score: float,
        transition: bool,
        previous_state: EmotionState | None,
    ) -> str:
        """Generate a human-readable state description.

        Args:
            state: Current emotion state.
            score: Sentiment score.
            transition: Whether state changed.
            previous_state: Previous state if transition.

        Returns:
            Description string.
        """
        descriptions = {
            EmotionState.EUPHORIA: "Extreme bullish sentiment - potential market top forming",
            EmotionState.OPTIMISM: "Strong positive sentiment - bullish momentum",
            EmotionState.HOPE: "Cautiously positive - early recovery signals",
            EmotionState.NEUTRAL: "Balanced sentiment - no strong directional bias",
            EmotionState.RELIEF: "Stress easing - bearish pressure fading",
            EmotionState.ANXIETY: "Growing unease - cautious positioning",
            EmotionState.FEAR: "Significant bearish sentiment - risk-off behavior",
            EmotionState.PANIC: "Intense selling pressure - capitulation risk",
            EmotionState.CAPITULATION: "Mass surrender - forced liquidation",
            EmotionState.DESPAIR: "Complete hopelessness - market bottom potential",
        }

        desc = descriptions.get(state, f"Unknown state: {state.value}")

        if transition and previous_state:
            desc += f" (transitioned from {previous_state.value})"

        return desc

    def clear(self) -> None:
        """Reset detector state."""
        self.current_state = EmotionState.NEUTRAL
        self.state_history.clear()
        self.score_history.clear()
