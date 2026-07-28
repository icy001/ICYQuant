"""NLP Sentiment Analyzer.

Analyzes text content to extract sentiment scores, classify polarity,
identify keywords, detect events, and perform semantic understanding.
Uses a lexicon-based approach with keyword and pattern matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import SentimentRecord, SentimentSource, SentimentLabel


# ---------------------------------------------------------------------------
# Sentiment Lexicon
# ---------------------------------------------------------------------------

BULLISH_KEYWORDS: dict[str, float] = {
    "strong": 0.6,
    "growth": 0.5,
    "beat": 0.7,
    "upgrade": 0.8,
    "buy": 0.6,
    "outperform": 0.7,
    "positive": 0.5,
    "bullish": 0.8,
    "rally": 0.7,
    "surge": 0.8,
    "breakout": 0.7,
    "momentum": 0.5,
    "innovation": 0.4,
    "expansion": 0.5,
    "profit": 0.6,
    "revenue growth": 0.7,
    "record high": 0.9,
    "all-time high": 0.9,
    "upside": 0.6,
    "catalyst": 0.5,
    "undervalued": 0.7,
    "accumulation": 0.6,
    "demand": 0.5,
    "leadership": 0.4,
    "partnership": 0.5,
    "dividend increase": 0.6,
    "buyback": 0.7,
    "guidance raised": 0.8,
}

BEARISH_KEYWORDS: dict[str, float] = {
    "weak": -0.6,
    "decline": -0.5,
    "miss": -0.7,
    "downgrade": -0.8,
    "sell": -0.6,
    "underperform": -0.7,
    "negative": -0.5,
    "bearish": -0.8,
    "crash": -0.9,
    "plunge": -0.8,
    "breakdown": -0.7,
    "risk": -0.4,
    "loss": -0.6,
    "debt": -0.4,
    "layoff": -0.7,
    "bankruptcy": -0.9,
    "lawsuit": -0.7,
    "investigation": -0.8,
    "scandal": -0.9,
    "warning": -0.7,
    "guidance cut": -0.8,
    "downturn": -0.6,
    "recession": -0.8,
    "volatility": -0.3,
    "uncertainty": -0.5,
    "overvalued": -0.7,
    "distribution": -0.6,
    "supply chain": -0.3,
    "short interest": -0.5,
}

EVENT_KEYWORDS: dict[str, str] = {
    "earnings": "earnings_report",
    "merger": "merger_acquisition",
    "acquisition": "merger_acquisition",
    "ipo": "ipo_event",
    "spin-off": "corporate_action",
    "split": "corporate_action",
    "dividend": "dividend_event",
    "ceo": "leadership_change",
    "cfo": "leadership_change",
    "regulation": "regulatory_event",
    "fda": "regulatory_event",
    "approval": "regulatory_event",
    "patent": "intellectual_property",
    "product launch": "product_event",
    "recall": "product_event",
    "partnership": "partnership_event",
    "contract": "contract_event",
    "restructuring": "restructuring_event",
    "layoff": "restructuring_event",
    "hiring": "workforce_event",
}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class NLPAnalysisResult:
    """Result of NLP sentiment analysis.

    Attributes:
        text: Original input text.
        score: Sentiment score [-1.0, 1.0].
        label: Classified sentiment label.
        confidence: Analysis confidence [0.0, 1.0].
        keywords_found: Detected keywords and their individual scores.
        events_detected: Detected event types.
        entities: Extracted entity names.
        summary: Brief analysis summary.
        language: Detected language.
        timestamp: Analysis timestamp.
    """

    text: str
    score: float = 0.0
    label: SentimentLabel = SentimentLabel.NEUTRAL
    confidence: float = 0.5
    keywords_found: dict[str, float] = field(default_factory=dict)
    events_detected: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    summary: str = ""
    language: str = "en"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_positive(self) -> bool:
        return self.score > 0.0

    @property
    def is_negative(self) -> bool:
        return self.score < 0.0

    @property
    def has_events(self) -> bool:
        return len(self.events_detected) > 0

    @property
    def keyword_count(self) -> int:
        return len(self.keywords_found)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class NLPAnalyzer:
    """NLP-based sentiment analyzer for financial text.

    Performs lexicon-based sentiment analysis with keyword detection,
    event extraction, entity recognition, and semantic scoring.

    Attributes:
        bullish_lexicon: Dictionary of bullish keywords and their weights.
        bearish_lexicon: Dictionary of bearish keywords and their weights.
        event_lexicon: Dictionary of event-trigger keywords.
        negation_words: Words that invert sentiment.
        intensifiers: Words that amplify sentiment.
    """

    def __init__(self) -> None:
        self.bullish_lexicon: dict[str, float] = dict(BULLISH_KEYWORDS)
        self.bearish_lexicon: dict[str, float] = dict(BEARISH_KEYWORDS)
        self.event_lexicon: dict[str, str] = dict(EVENT_KEYWORDS)

        self.negation_words: set[str] = {
            "not",
            "no",
            "never",
            "neither",
            "nor",
            "nothing",
            "without",
            "hardly",
            "barely",
            "scarcely",
        }

        self.intensifiers: dict[str, float] = {
            "very": 1.5,
            "extremely": 2.0,
            "highly": 1.5,
            "significantly": 1.5,
            "substantially": 1.5,
            "remarkably": 1.8,
            "exceptionally": 1.8,
            "massively": 2.0,
            "dramatically": 1.7,
            "tremendously": 1.8,
        }

    # --- Public API ---

    def analyze(self, text: str, source: SentimentSource | None = None) -> NLPAnalysisResult:
        """Analyze the sentiment of a text.

        Args:
            text: Text content to analyze.
            source: Optional source hint for context.

        Returns:
            NLPAnalysisResult with score, label, keywords, and events.
        """
        if not text or not text.strip():
            return NLPAnalysisResult(text=text or "", summary="Empty input.")

        text_lower = text.lower()

        # Keyword detection
        bullish_found = self._match_keywords(text_lower, self.bullish_lexicon)
        bearish_found = self._match_keywords(text_lower, self.bearish_lexicon)

        all_keywords = {**bullish_found, **bearish_found}

        # Compute raw score
        raw_score = sum(all_keywords.values())
        keyword_count = len(all_keywords)

        if keyword_count > 0:
            raw_score = raw_score / keyword_count  # Normalize by count
        else:
            raw_score = 0.0

        # Apply negation and intensifiers
        raw_score = self._apply_negation(text_lower, raw_score)
        raw_score = self._apply_intensifiers(text_lower, raw_score)

        # Clamp
        score = max(-1.0, min(1.0, raw_score))

        # Determine label
        label = self._score_to_label(score)

        # Confidence based on keyword density and agreement
        confidence = self._compute_confidence(bullish_found, bearish_found, text)

        # Event detection
        events = self._detect_events(text_lower)

        # Entity extraction (simple capitalization heuristic)
        entities = self._extract_entities(text)

        # Summary
        summary = self._generate_summary(score, label, events, all_keywords)

        return NLPAnalysisResult(
            text=text,
            score=score,
            label=label,
            confidence=confidence,
            keywords_found=all_keywords,
            events_detected=events,
            entities=entities,
            summary=summary,
        )

    def analyze_batch(
        self, texts: list[str], source: SentimentSource | None = None
    ) -> list[NLPAnalysisResult]:
        """Analyze a batch of texts.

        Args:
            texts: List of text content to analyze.
            source: Optional source hint.

        Returns:
            List of NLPAnalysisResult, one per input text.
        """
        return [self.analyze(text, source) for text in texts]

    def analyze_record(self, record: SentimentRecord) -> NLPAnalysisResult:
        """Analyze a SentimentRecord and update its score/label.

        Args:
            record: SentimentRecord to analyze.

        Returns:
            NLPAnalysisResult with analysis details.
        """
        result = self.analyze(record.content, record.source)
        record.score = result.score
        record.label = result.label
        record.confidence = result.confidence
        return result

    def add_keyword(self, keyword: str, weight: float, bullish: bool = True) -> None:
        """Add a custom keyword to the lexicon.

        Args:
            keyword: The keyword phrase.
            weight: Sentiment weight (absolute value used).
            bullish: True to add to bullish, False for bearish.
        """
        lexicon = self.bullish_lexicon if bullish else self.bearish_lexicon
        lexicon[keyword.lower()] = abs(weight) if bullish else -abs(weight)

    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword from both lexicons.

        Args:
            keyword: The keyword phrase to remove.
        """
        kw = keyword.lower()
        self.bullish_lexicon.pop(kw, None)
        self.bearish_lexicon.pop(kw, None)

    # --- Internal Methods ---

    def _match_keywords(
        self, text_lower: str, lexicon: dict[str, float]
    ) -> dict[str, float]:
        """Find matching keywords in text.

        Args:
            text_lower: Lowercased text.
            lexicon: Keyword-weight dictionary.

        Returns:
            Dict of matched keywords and their weights.
        """
        matched: dict[str, float] = {}
        for keyword, weight in sorted(lexicon.items(), key=lambda x: -len(x[0])):
            if keyword in text_lower:
                matched[keyword] = weight
        return matched

    def _apply_negation(self, text_lower: str, score: float) -> float:
        """Check for negation words that invert sentiment.

        Args:
            text_lower: Lowercased text.
            score: Current sentiment score.

        Returns:
            Adjusted score.
        """
        words = text_lower.split()
        for i, word in enumerate(words):
            if word in self.negation_words:
                # Check if a sentiment keyword follows within 3 words
                window = words[i + 1 : i + 4]
                window_text = " ".join(window)
                if any(kw in window_text for kw in self.bullish_lexicon) or any(
                    kw in window_text for kw in self.bearish_lexicon
                ):
                    return -score
        return score

    def _apply_intensifiers(self, text_lower: str, score: float) -> float:
        """Apply intensifier multipliers.

        Args:
            text_lower: Lowercased text.
            score: Current sentiment score.

        Returns:
            Adjusted score.
        """
        max_multiplier = 1.0
        for word, multiplier in self.intensifiers.items():
            if word in text_lower:
                max_multiplier = max(max_multiplier, multiplier)
        return max(-1.0, min(1.0, score * max_multiplier))

    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert a numeric score to a sentiment label.

        Args:
            score: Sentiment score [-1.0, 1.0].

        Returns:
            Corresponding SentimentLabel.
        """
        if score >= 0.8:
            return SentimentLabel.VERY_BULLISH
        elif score >= 0.5:
            return SentimentLabel.BULLISH
        elif score >= 0.2:
            return SentimentLabel.SLIGHTLY_BULLISH
        elif score > -0.2:
            return SentimentLabel.NEUTRAL
        elif score > -0.5:
            return SentimentLabel.SLIGHTLY_BEARISH
        elif score > -0.8:
            return SentimentLabel.BEARISH
        else:
            return SentimentLabel.VERY_BEARISH

    def _compute_confidence(
        self,
        bullish_found: dict[str, float],
        bearish_found: dict[str, float],
        text: str,
    ) -> float:
        """Compute analysis confidence based on keyword density and agreement.

        Args:
            bullish_found: Matched bullish keywords.
            bearish_found: Matched bearish keywords.
            text: Original text.

        Returns:
            Confidence score [0.0, 1.0].
        """
        total_keywords = len(bullish_found) + len(bearish_found)
        if total_keywords == 0:
            return 0.1

        # More keywords = higher confidence (up to a point)
        keyword_confidence = min(1.0, total_keywords / 5.0)

        # Agreement confidence: all bullish or all bearish is more confident
        if len(bullish_found) > 0 and len(bearish_found) == 0:
            agreement = 1.0
        elif len(bearish_found) > 0 and len(bullish_found) == 0:
            agreement = 1.0
        else:
            # Mixed signals reduce confidence
            dominant = max(len(bullish_found), len(bearish_found))
            agreement = dominant / total_keywords

        return 0.4 * keyword_confidence + 0.6 * agreement

    def _detect_events(self, text_lower: str) -> list[str]:
        """Detect financial events mentioned in text.

        Args:
            text_lower: Lowercased text.

        Returns:
            List of detected event types (deduplicated).
        """
        events: list[str] = []
        for keyword, event_type in self.event_lexicon.items():
            if keyword in text_lower and event_type not in events:
                events.append(event_type)
        return events

    def _extract_entities(self, text: str) -> list[str]:
        """Extract entity names using capitalization heuristic.

        Args:
            text: Original text.

        Returns:
            List of detected entity names.
        """
        entities: list[str] = []
        words = text.split()
        i = 0
        while i < len(words):
            word = words[i].strip(".,!?;:'\"()[]{}")
            # Detect ticker symbols ($AAPL, $TSLA)
            if word.startswith("$") and len(word) > 1:
                entities.append(word[1:].upper())
            # Detect capitalized multi-word entities
            elif word and word[0].isupper() and len(word) > 1 and word.isalpha():
                entity_parts = [word]
                j = i + 1
                while j < len(words):
                    next_word = words[j].strip(".,!?;:'\"()[]{}")
                    if next_word and next_word[0].isupper() and next_word.isalpha():
                        entity_parts.append(next_word)
                        j += 1
                    else:
                        break
                entity = " ".join(entity_parts)
                if len(entity_parts) >= 2 or word.upper() == word:
                    entities.append(entity)
                i = j - 1
            i += 1
        return list(dict.fromkeys(entities))  # Deduplicate preserving order

    def _generate_summary(
        self,
        score: float,
        label: SentimentLabel,
        events: list[str],
        keywords: dict[str, float],
    ) -> str:
        """Generate a human-readable analysis summary.

        Args:
            score: Sentiment score.
            label: Sentiment label.
            events: Detected events.
            keywords: Matched keywords.

        Returns:
            Summary string.
        """
        parts = [f"Sentiment: {label.value} (score={score:.2f})"]

        if keywords:
            top_keywords = sorted(keywords.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            kw_str = ", ".join(f"{k}({v:+.1f})" for k, v in top_keywords)
            parts.append(f"Keywords: {kw_str}")

        if events:
            parts.append(f"Events: {', '.join(events)}")

        return " | ".join(parts)

    def clear(self) -> None:
        """Reset custom lexicon additions (does not clear built-in lexicons)."""
        self.bullish_lexicon = dict(BULLISH_KEYWORDS)
        self.bearish_lexicon = dict(BEARISH_KEYWORDS)
