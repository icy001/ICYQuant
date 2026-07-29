"""Experience Replay Engine - replay past experiences for learning."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import random


class ReplayMode(Enum):
    """Mode for experience replay."""
    SEQUENTIAL = "SEQUENTIAL"
    RANDOM = "RANDOM"
    PRIORITIZED = "PRIORITIZED"
    STRATIFIED = "STRATIFIED"
    RECENCY = "RECENCY"


class ReplayPhase(Enum):
    """Phase of replay analysis."""
    INITIALIZATION = "INITIALIZATION"
    REPLAYING = "REPLAYING"
    ANALYSIS = "ANALYSIS"
    COMPLETED = "COMPLETED"


@dataclass
class ReplayResult:
    """Result of a single replay operation."""
    replay_id: str
    experience_id: str
    original_outcome: str
    simulated_outcome: str
    match: bool
    insight: str
    confidence: float


@dataclass
class ReplayBatch:
    """A batch of replay results."""
    batch_id: str
    results: List[ReplayResult] = field(default_factory=list)
    mode: ReplayMode = ReplayMode.RANDOM
    phase: ReplayPhase = ReplayPhase.INITIALIZATION

    @property
    def match_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.match) / len(self.results)

    @property
    def avg_confidence(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.confidence for r in self.results) / len(self.results)


class ExperienceReplayEngine:
    """Experience Replay Engine.

    Replays past trading experiences for learning, similar to
    reinforcement learning experience replay:
    - Historical scenario replay
    - Error reproduction
    - Strategy optimization
    - Pattern validation
    """

    def __init__(self, buffer_size: int = 1000):
        self.buffer_size = buffer_size
        self.experience_buffer: List[Dict[str, Any]] = []
        self.replay_history: List[ReplayBatch] = []
        self._replay_counter = 0

    def replay(self, history: List[Dict[str, Any]],
               mode: ReplayMode = ReplayMode.RANDOM,
               batch_size: int = 32) -> Dict[str, Any]:
        """Replay historical experiences.

        Args:
            history: List of historical experience data.
            mode: Replay sampling mode.
            batch_size: Number of experiences to replay.

        Returns:
            Dict with replay results.
        """
        if not history:
            return {
                "status": "EMPTY",
                "results": [],
                "batch_size": 0,
            }

        # Add to buffer
        for exp in history:
            self.experience_buffer.append(exp)
            if len(self.experience_buffer) > self.buffer_size:
                self.experience_buffer.pop(0)

        # Sample batch based on mode
        batch = self._sample_batch(batch_size, mode)

        # Replay each experience
        results = []
        for exp in batch:
            result = self._replay_single(exp)
            results.append(result)

        batch_record = ReplayBatch(
            batch_id=f"REPLAY_{self._replay_counter:04d}",
            results=results,
            mode=mode,
            phase=ReplayPhase.COMPLETED,
        )
        self.replay_history.append(batch_record)
        self._replay_counter += 1

        return {
            "status": "COMPLETED",
            "batch_id": batch_record.batch_id,
            "mode": mode.value,
            "results": [
                {
                    "experience_id": r.experience_id,
                    "original_outcome": r.original_outcome,
                    "simulated_outcome": r.simulated_outcome,
                    "match": r.match,
                    "insight": r.insight,
                    "confidence": r.confidence,
                }
                for r in results
            ],
            "match_rate": batch_record.match_rate,
            "avg_confidence": batch_record.avg_confidence,
            "buffer_size": len(self.experience_buffer),
        }

    def _sample_batch(self, batch_size: int,
                      mode: ReplayMode) -> List[Dict[str, Any]]:
        """Sample a batch from the buffer based on mode."""
        buffer = self.experience_buffer
        size = min(batch_size, len(buffer))

        if mode == ReplayMode.SEQUENTIAL:
            return buffer[-size:]
        elif mode == ReplayMode.RANDOM:
            return random.sample(buffer, size)
        elif mode == ReplayMode.PRIORITIZED:
            # Prioritize high-importance experiences
            sorted_buffer = sorted(
                buffer,
                key=lambda e: abs(e.get("pnl", 0.0)) * e.get("importance", 1.0),
                reverse=True,
            )
            return sorted_buffer[:size]
        elif mode == ReplayMode.STRATIFIED:
            # Stratify by outcome
            positive = [e for e in buffer if e.get("outcome") == "POSITIVE"]
            negative = [e for e in buffer if e.get("outcome") == "NEGATIVE"]
            neutral = [e for e in buffer if e.get("outcome") not in ("POSITIVE", "NEGATIVE")]
            half = size // 2
            neg_count = min(len(negative), half)
            pos_count = min(len(positive), size - neg_count)
            return (random.sample(negative, neg_count) +
                    random.sample(positive, pos_count))
        elif mode == ReplayMode.RECENCY:
            return buffer[-size:]
        return random.sample(buffer, size)

    def _replay_single(self, experience: Dict[str, Any]) -> ReplayResult:
        """Replay a single experience and generate insight."""
        exp_id = experience.get("id", "unknown")
        original_outcome = experience.get("outcome", "NEUTRAL")
        pnl = experience.get("pnl", 0.0)

        # Simulate re-evaluating this experience
        context = experience.get("context", {})
        market_regime = context.get("market_regime", "normal")
        volatility = context.get("volatility", 0.15)
        strategy = experience.get("strategy", "unknown")

        # In simulated re-evaluation, check if the decision made sense
        simulated_outcome = original_outcome
        if abs(pnl) < 0.001 and market_regime != "normal":
            simulated_outcome = "NEUTRAL"

        match = simulated_outcome == original_outcome

        # Generate insight based on analysis
        if match and original_outcome == "POSITIVE":
            insight = f"Confirmed: {strategy} performed well in {market_regime} regime"
        elif match and original_outcome == "NEGATIVE":
            insight = f"Confirmed: {strategy} struggled in {market_regime} regime"
        elif not match:
            insight = f"Re-evaluation differs: market regime {market_regime} may have influenced outcome"
        else:
            insight = "Neutral outcome, low information value"

        confidence = 0.7 if match else 0.3

        return ReplayResult(
            replay_id=f"R_{self._replay_counter:04d}",
            experience_id=exp_id,
            original_outcome=original_outcome,
            simulated_outcome=simulated_outcome,
            match=match,
            insight=insight,
            confidence=confidence,
        )

    def replay_scenario(self, scenario: Dict[str, Any],
                        decision_fn: Callable) -> Dict[str, Any]:
        """Replay a specific market scenario with a decision function.

        Args:
            scenario: Market scenario data.
            decision_fn: Function that takes scenario and returns decision.

        Returns:
            Dict with scenario replay analysis.
        """
        decision = decision_fn(scenario)
        expected_outcome = scenario.get("expected_outcome", "NEUTRAL")
        match = decision.get("action") == scenario.get("optimal_action", "")

        return {
            "scenario": scenario.get("name", "unknown"),
            "decision": decision,
            "expected": expected_outcome,
            "match": match,
            "market_context": scenario.get("context", {}),
            "lessons": [f"Decision {'correct' if match else 'incorrect'} for {scenario.get('name')}"],
        }

    def get_replay_statistics(self) -> Dict[str, Any]:
        """Get statistics over all replays.

        Returns:
            Dict with replay statistics.
        """
        if not self.replay_history:
            return {"total_replays": 0}

        all_results = [r for batch in self.replay_history for r in batch.results]
        return {
            "total_replays": len(self.replay_history),
            "total_results": len(all_results),
            "overall_match_rate": (sum(1 for r in all_results if r.match) /
                                   max(len(all_results), 1)),
            "avg_confidence": (sum(r.confidence for r in all_results) /
                              max(len(all_results), 1)),
            "buffer_utilization": len(self.experience_buffer) / max(self.buffer_size, 1),
            "insights_collected": len([r for r in all_results if r.insight]),
        }

    def extract_key_lessons(self) -> List[str]:
        """Extract key lessons from all replays.

        Returns:
            List of lesson strings.
        """
        lessons = []
        for batch in self.replay_history:
            for r in batch.results:
                if r.insight:
                    lessons.append(r.insight)
        return list(dict.fromkeys(lessons))  # deduplicate preserving order
