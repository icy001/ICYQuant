"""Trading Learning Service – unified API for trade review and learning."""

from typing import Any, Dict, List, Optional

from .trade_result import TradeResult
from .outcome import OutcomeAnalyzer, OutcomeReport
from .feedback import StrategyFeedbackEngine, StrategyFeedback
from .mistake import MistakeDetector, MistakeReport
from .memory import LearningMemory, LearningRecord
from .attribution import AttributionEngine, AttributionResult
from .journal import TradingJournalGenerator, JournalEntry


class TradingLearningService:
    """Unified service for AI-powered trade review and continuous learning.

    Integrates outcome analysis, strategy feedback, mistake detection,
    learning memory, performance attribution, and journal generation
    into a complete learning feedback loop.

    Typical workflow:
        trade completed → review → analyze → detect mistakes →
        extract lessons → store memory → generate feedback →
        generate journal → feed back to strategies
    """

    def __init__(
        self,
        analyzer: Optional[OutcomeAnalyzer] = None,
        feedback: Optional[StrategyFeedbackEngine] = None,
        detector: Optional[MistakeDetector] = None,
        memory: Optional[LearningMemory] = None,
        attribution: Optional[AttributionEngine] = None,
        journal: Optional[TradingJournalGenerator] = None,
    ):
        self._analyzer = analyzer or OutcomeAnalyzer()
        self._feedback = feedback or StrategyFeedbackEngine()
        self._detector = detector or MistakeDetector()
        self._memory = memory or LearningMemory()
        self._attribution = attribution or AttributionEngine()
        self._journal = journal or TradingJournalGenerator()

    # ------------------------------------------------------------------
    # Trade Review
    # ------------------------------------------------------------------

    def review(self, trade: TradeResult) -> dict:
        """Review a completed trade (legacy interface)."""
        return self._analyzer.analyze(trade)

    def review_detailed(self, trade: TradeResult) -> OutcomeReport:
        """Detailed trade outcome analysis."""
        return self._analyzer.analyze_detailed(trade)

    def review_batch(self, trades: List[TradeResult]) -> List[OutcomeReport]:
        """Review a batch of trades."""
        return self._analyzer.analyze_batch(trades)

    def review_summary(self, reports: List[OutcomeReport]) -> dict:
        """Summarize review results."""
        return self._analyzer.batch_summary(reports)

    # ------------------------------------------------------------------
    # Strategy Feedback
    # ------------------------------------------------------------------

    def strategy_feedback(
        self,
        trades: List[TradeResult],
        strategy_name: str = "",
        strategy_id: str = "",
    ) -> StrategyFeedback:
        """Generate feedback for a strategy based on its trade history."""
        return self._feedback.generate(trades, strategy_name, strategy_id)

    # ------------------------------------------------------------------
    # Mistake Detection
    # ------------------------------------------------------------------

    def detect_mistakes(self, trade: TradeResult) -> list:
        """Detect trading mistakes."""
        return self._detector.detect(trade)

    def detect_mistakes_detailed(self, trade: TradeResult) -> MistakeReport:
        """Detailed mistake detection."""
        return self._detector.detect_detailed(trade)

    def detect_mistakes_batch(self, trades: List[TradeResult]) -> List[MistakeReport]:
        """Detect mistakes across multiple trades."""
        return self._detector.detect_batch(trades)

    def mistake_summary(self, reports: List[MistakeReport]) -> dict:
        """Summarize mistake reports."""
        return self._detector.batch_summary(reports)

    # ------------------------------------------------------------------
    # Learning Memory
    # ------------------------------------------------------------------

    def store_learning(
        self,
        trade: TradeResult,
        quality_score: float = 0.0,
        mistakes: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        lesson: str = "",
        tags: Optional[List[str]] = None,
    ) -> LearningRecord:
        """Store a learning record from a trade."""
        return self._memory.store_trade_result(
            trade, quality_score, mistakes, strengths, lesson, tags,
        )

    def query_learning(self, symbol: str = "", strategy_id: str = "",
                       outcome: str = "", regime: str = "",
                       tag: str = "") -> List[LearningRecord]:
        """Query learning records with filters."""
        if symbol:
            return self._memory.query_by_symbol(symbol)
        if strategy_id:
            return self._memory.query_by_strategy(strategy_id)
        if outcome:
            return self._memory.query_by_outcome(outcome)
        if regime:
            return self._memory.query_by_market_regime(regime)
        if tag:
            return self._memory.query_by_tag(tag)
        return self._memory.get_all()

    def learning_summary(self) -> dict:
        """Get learning memory summary."""
        return self._memory.summary()

    # ------------------------------------------------------------------
    # Performance Attribution
    # ------------------------------------------------------------------

    def attribute(
        self,
        trade: TradeResult,
        market_return_pct: float = 0.0,
        sector_return_pct: float = 0.0,
        beta: float = 1.0,
    ) -> dict:
        """Attribute trade performance."""
        return self._attribution.analyze(trade, market_return_pct,
                                         sector_return_pct, beta)

    def attribute_detailed(
        self,
        trade: TradeResult,
        market_return_pct: float = 0.0,
        sector_return_pct: float = 0.0,
        beta: float = 1.0,
    ) -> AttributionResult:
        """Detailed performance attribution."""
        return self._attribution.analyze_detailed(
            trade, market_return_pct, sector_return_pct, beta,
        )

    def attribute_batch(
        self,
        trades: List[TradeResult],
        market_returns: Optional[List[float]] = None,
        sector_returns: Optional[List[float]] = None,
        betas: Optional[List[float]] = None,
    ) -> List[AttributionResult]:
        """Attribute performance for multiple trades."""
        return self._attribution.analyze_batch(trades, market_returns,
                                               sector_returns, betas)

    def attribute_aggregate(self, results: List[AttributionResult]) -> dict:
        """Aggregate attribution results."""
        return self._attribution.aggregate(results)

    # ------------------------------------------------------------------
    # Trading Journal
    # ------------------------------------------------------------------

    def generate_journal(
        self,
        trade: TradeResult,
        thesis: str = "",
        entry_reason: str = "",
        exit_reason: str = "",
        lesson: str = "",
        improvement_plan: str = "",
    ) -> JournalEntry:
        """Generate a trading journal entry."""
        return self._journal.generate(
            trade, thesis, entry_reason, exit_reason, lesson, improvement_plan,
        )

    def generate_journal_batch(
        self,
        trades: List[TradeResult],
    ) -> List[JournalEntry]:
        """Generate journal entries for multiple trades."""
        return self._journal.generate_batch(trades)

    # ------------------------------------------------------------------
    # Full Learning Loop
    # ------------------------------------------------------------------

    def learn(
        self,
        trade: TradeResult,
        market_return_pct: float = 0.0,
        sector_return_pct: float = 0.0,
        beta: float = 1.0,
        thesis: str = "",
        entry_reason: str = "",
        exit_reason: str = "",
    ) -> dict:
        """Run the complete learning feedback loop for a single trade.

        1. Review outcome
        2. Attribute performance
        3. Detect mistakes
        4. Store learning
        5. Generate journal

        Returns a comprehensive learning report.
        """
        # 1. Review outcome
        outcome = self.review_detailed(trade)

        # 2. Attribute performance
        attribution = self.attribute_detailed(trade, market_return_pct,
                                              sector_return_pct, beta)

        # 3. Detect mistakes
        mistakes = self.detect_mistakes_detailed(trade)

        # 4. Store learning
        lesson = self._derive_lesson(outcome, mistakes, attribution)
        record = self.store_learning(
            trade=trade,
            quality_score=outcome.score,
            mistakes=mistakes.mistakes if mistakes.mistakes != ["none"] else [],
            strengths=outcome.strengths,
            lesson=lesson,
            tags=self._derive_tags(trade, outcome),
        )

        # 5. Generate journal
        journal = self.generate_journal(
            trade, thesis=thesis, entry_reason=entry_reason,
            exit_reason=exit_reason, lesson=lesson,
            improvement_plan=self._derive_improvement_plan(mistakes, outcome),
        )

        return {
            "outcome": outcome.to_dict(),
            "attribution": attribution.to_dict(),
            "mistakes": mistakes.to_dict(),
            "learning_record": record.to_dict(),
            "journal": journal.to_dict(),
            "lesson": lesson,
        }

    def learn_batch(
        self,
        trades: List[TradeResult],
        market_returns: Optional[List[float]] = None,
        sector_returns: Optional[List[float]] = None,
        betas: Optional[List[float]] = None,
    ) -> dict:
        """Run the learning loop for a batch of trades."""
        results = [self.learn(
            t,
            market_return_pct=market_returns[i] if market_returns and i < len(market_returns) else 0.0,
            sector_return_pct=sector_returns[i] if sector_returns and i < len(sector_returns) else 0.0,
            beta=betas[i] if betas and i < len(betas) else 1.0,
        ) for i, t in enumerate(trades)]

        # Aggregate
        outcomes = [self.review_detailed(t) for t in trades]
        attributions = [self.attribute_detailed(
            t,
            market_returns[i] if market_returns and i < len(market_returns) else 0.0,
            sector_returns[i] if sector_returns and i < len(sector_returns) else 0.0,
            betas[i] if betas and i < len(betas) else 1.0,
        ) for i, t in enumerate(trades)]

        return {
            "individual_results": results,
            "outcome_summary": self.review_summary(outcomes),
            "attribution_aggregate": self.attribute_aggregate(attributions),
            "learning_summary": self.learning_summary(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _derive_lesson(self, outcome: OutcomeReport,
                       mistakes: MistakeReport,
                       attribution: AttributionResult) -> str:
        """Derive a learning lesson from analysis results."""
        parts = []

        if outcome.quality == "excellent":
            parts.append(f"Excellent trade – {outcome.outcome_category}.")
        elif outcome.quality == "good":
            parts.append(f"Solid trade – {outcome.outcome_category}.")
        else:
            parts.append(f"Review needed – {outcome.outcome_category}.")

        if attribution.alpha > 0:
            parts.append(f"Alpha contributed {attribution.alpha:+.1f}%.")
        if attribution.execution < -0.1:
            parts.append(f"Execution cost: {abs(attribution.execution):.1f}%.")

        if mistakes.has_mistakes():
            parts.append(f"Detected {mistakes.error_count} issue(s).")

        return " ".join(parts)

    def _derive_tags(self, trade: TradeResult,
                     outcome: OutcomeReport) -> List[str]:
        """Derive learning tags."""
        tags = list(trade.tags)
        tags.append(trade.outcome)
        tags.append(outcome.quality)
        tags.append(outcome.outcome_category)
        if trade.market_regime:
            tags.append(trade.market_regime)
        return list(set(tags))

    def _derive_improvement_plan(self, mistakes: MistakeReport,
                                 outcome: OutcomeReport) -> str:
        """Derive an improvement plan."""
        if outcome.quality in ("excellent", "good"):
            return "Continue current approach. Document for repeatability."
        if mistakes.has_mistakes():
            return f"Address {mistakes.error_count} detected issues: " + \
                   "; ".join(mistakes.mistakes[:3])
        return "Review trade thesis and risk parameters."
