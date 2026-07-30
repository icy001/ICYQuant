"""
Financial NLP Processor.

Processes financial text for:
- Text classification
- Keyword extraction
- Topic identification
- Summarization
- Similar text search
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class NLPTask(str, Enum):
    CLASSIFICATION = "classification"
    KEYWORD_EXTRACTION = "keyword_extraction"
    TOPIC_IDENTIFICATION = "topic_identification"
    SUMMARIZATION = "summarization"
    NAMED_ENTITY = "named_entity"
    RELATION_EXTRACTION = "relation_extraction"


class NLPTopic(str, Enum):
    EARNINGS = "earnings"
    M_AND_A = "merger_acquisition"
    PRODUCT_LAUNCH = "product_launch"
    REGULATION = "regulation"
    MACRO = "macro"
    TECHNOLOGY = "technology"
    SUPPLY_CHAIN = "supply_chain"
    MANAGEMENT = "management"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    DIVIDEND = "dividend"
    ESG = "esg"
    GEOPOLITICAL = "geopolitical"
    CURRENCY = "currency"
    COMMODITY = "commodity"
    SECTOR_ROTATION = "sector_rotation"
    OTHER = "other"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class NLPResult:
    """Result of NLP processing on a document."""

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    task: NLPTask = NLPTask.CLASSIFICATION

    # Classification
    topics: List[NLPTopic] = field(default_factory=list)
    topic_scores: Dict[str, float] = field(default_factory=dict)

    # Keywords
    keywords: List[str] = field(default_factory=list)
    keyword_scores: Dict[str, float] = field(default_factory=dict)

    # Summary
    summary: str = ""

    # Entities (delegated to entity_extraction for full extraction)
    entities_mentioned: List[str] = field(default_factory=list)

    # Metadata
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Direction / polarity
    direction: str = "neutral"  # positive, negative, neutral
    direction_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "document_id": self.document_id,
            "task": self.task.value,
            "topics": [t.value for t in self.topics],
            "topic_scores": self.topic_scores,
            "keywords": self.keywords,
            "keyword_scores": self.keyword_scores,
            "summary": self.summary,
            "entities_mentioned": self.entities_mentioned,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "processed_at": self.processed_at.isoformat(),
            "direction": self.direction,
            "direction_confidence": self.direction_confidence,
        }


@dataclass
class NLPConfig:
    """Configuration for NLP processor."""

    # Keyword extraction
    max_keywords: int = 15
    min_keyword_score: float = 0.1

    # Summarization
    max_summary_length: int = 200

    # Topic classification
    min_topic_confidence: float = 0.3
    max_topics: int = 3

    # Language
    default_language: str = "en"

    # Performance
    max_text_length: int = 10000


# ── Financial Lexicon ────────────────────────────────────────────────────────

# Topic-indicative keywords
TOPIC_KEYWORDS: Dict[NLPTopic, List[str]] = {
    NLPTopic.EARNINGS: [
        "earnings", "revenue", "profit", "eps", "earnings per share",
        "net income", "gross margin", "operating income", "bottom line",
        "quarterly results", "annual results", "beat estimates", "missed estimates",
        "收入", "利润", "净利润", "每股收益", "财报", "业绩",
    ],
    NLPTopic.M_AND_A: [
        "acquisition", "merger", "takeover", "buyout", "consolidation",
        "acquired", "merging", "deal", "transaction", "synergies",
        "收购", "并购", "合并", "重组",
    ],
    NLPTopic.PRODUCT_LAUNCH: [
        "launch", "new product", "release", "unveiled", "announced",
        "next generation", "upgrade", "version", "model",
        "发布", "新品", "推出", "上线",
    ],
    NLPTopic.REGULATION: [
        "regulation", "regulatory", "compliance", "sec", "ftc", "antitrust",
        "investigation", "fine", "penalty", "lawsuit", "ruling",
        "监管", "法规", "合规", "调查", "处罚",
    ],
    NLPTopic.MACRO: [
        "gdp", "inflation", "cpi", "ppi", "interest rate", "fed",
        "monetary policy", "fiscal policy", "unemployment", "pmi",
        "gdp", "通胀", "利率", "央行", "货币政策",
    ],
    NLPTopic.TECHNOLOGY: [
        "ai", "artificial intelligence", "machine learning", "blockchain",
        "cloud", "semiconductor", "chip", "gpu", "quantum",
        "人工智能", "芯片", "云计算", "半导体",
    ],
    NLPTopic.SUPPLY_CHAIN: [
        "supply chain", "supplier", "logistics", "shortage", "inventory",
        "procurement", "manufacturing", "production", "capacity",
        "供应链", "供应商", "产能", "库存",
    ],
    NLPTopic.MANAGEMENT: [
        "ceo", "cfo", "executive", "board", "management change",
        "appointed", "resigned", "leadership", "restructuring",
        "任命", "辞职", "高管", "管理层",
    ],
    NLPTopic.CAPITAL_EXPENDITURE: [
        "capex", "capital expenditure", "investment", "spending",
        "expansion", "build", "construction", "facility",
        "资本开支", "投资", "扩建",
    ],
    NLPTopic.DIVIDEND: [
        "dividend", "buyback", "share repurchase", "payout",
        "yield", "distribution",
        "分红", "回购", "股息",
    ],
    NLPTopic.ESG: [
        "esg", "sustainability", "carbon", "emission", "green",
        "renewable", "governance", "diversity",
        "esg", "可持续", "碳排放", "绿色",
    ],
    NLPTopic.GEOPOLITICAL: [
        "war", "conflict", "sanction", "tariff", "trade war",
        "embargo", "diplomatic", "tension",
        "战争", "制裁", "关税", "冲突",
    ],
    NLPTopic.CURRENCY: [
        "forex", "currency", "exchange rate", "dollar", "yuan",
        "euro", "yen", "devaluation", "appreciation",
        "汇率", "美元", "人民币", "升值", "贬值",
    ],
    NLPTopic.COMMODITY: [
        "oil", "gold", "copper", "commodity", "crude", "metal",
        "energy", "agriculture", "iron ore", "lithium",
        "石油", "黄金", "铜", "大宗商品", "能源",
    ],
    NLPTopic.SECTOR_ROTATION: [
        "sector rotation", "rotation", "cyclical", "defensive",
        "growth", "value", "momentum", "style",
        "板块轮动", "行业轮动",
    ],
}

# Direction-indicative keywords
POSITIVE_KEYWORDS: Set[str] = {
    "beat", "exceed", "growth", "increase", "improve", "positive",
    "upgrade", "outperform", "strong", "record", "surge", "soar",
    "bullish", "optimistic", "expansion", "opportunity", "breakthrough",
    "增长", "提升", "超预期", "利好", "突破", "创新高",
    "上调", "强劲", "改善", "扩张", "机遇",
}

NEGATIVE_KEYWORDS: Set[str] = {
    "miss", "decline", "decrease", "loss", "negative", "downgrade",
    "underperform", "weak", "drop", "plunge", "crash", "bearish",
    "pessimistic", "risk", "warning", "concern", "crisis",
    "layoff", "bankruptcy", "default", "lawsuit", "investigation",
    "下跌", "下降", "亏损", "风险", "危机", "下调",
    "疲软", "萎缩", "衰退", "警告", "利空",
}

# Common stop words for keyword filtering
STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "and", "but", "or", "nor", "not", "so",
    "yet", "both", "either", "neither", "each", "every", "all",
    "any", "few", "more", "most", "other", "some", "such", "no",
    "only", "own", "same", "than", "too", "very", "just", "about",
    "its", "it", "this", "that", "these", "those", "they", "them",
    "their", "he", "she", "his", "her", "we", "our", "you", "your",
    "的", "了", "在", "是", "我", "有", "和", "就",
    "不", "人", "都", "一", "一个", "上", "也", "很",
    "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这",
}


# ── NLP Processor ────────────────────────────────────────────────────────────

class NLPProcessor:
    """
    Financial NLP processor with keyword-based classification and
    light-weight text analysis. Designed to work with external NLP
    models via pluggable backends.

    Supports:
    - Topic classification via financial lexicon
    - Keyword extraction via TF-like scoring
    - Basic summarization (extractive)
    - Direction/polarity detection
    """

    def __init__(self, config: Optional[NLPConfig] = None):
        self.config = config or NLPConfig()
        self._results: List[NLPResult] = []

    # ── Main Processing ──────────────────────────────────────────────────────

    def process(
        self,
        document_id: str,
        text: str,
        tasks: Optional[List[NLPTask]] = None,
        language: str = "en",
    ) -> NLPResult:
        """
        Process text through specified NLP tasks.

        Args:
            document_id: Unique identifier for the document.
            text: Raw text to process.
            tasks: List of NLP tasks to run. Defaults to all.
            language: Text language hint.

        Returns:
            NLPResult with all requested analysis.
        """
        import time
        start_time = time.time()

        if tasks is None:
            tasks = list(NLPTask)

        # Truncate text if too long
        if len(text) > self.config.max_text_length:
            text = text[: self.config.max_text_length]

        text_lower = text.lower()
        result = NLPResult(
            document_id=document_id,
            task=NLPTask.CLASSIFICATION,
        )

        # Topic classification
        if NLPTask.TOPIC_IDENTIFICATION in tasks:
            result.topics, result.topic_scores = self._classify_topics(text_lower)

        # Keyword extraction
        if NLPTask.KEYWORD_EXTRACTION in tasks:
            result.keywords, result.keyword_scores = self._extract_keywords(text_lower)

        # Summarization
        if NLPTask.SUMMARIZATION in tasks:
            result.summary = self._summarize(text)

        # Direction detection (part of classification)
        if NLPTask.CLASSIFICATION in tasks:
            result.direction, result.direction_confidence = self._detect_direction(
                text_lower
            )

        # Compute overall confidence
        result.confidence = self._compute_confidence(result)

        result.processing_time_ms = (time.time() - start_time) * 1000
        self._results.append(result)

        logger.debug(
            f"NLP processed doc={document_id}: topics={result.topics}, "
            f"direction={result.direction}, confidence={result.confidence:.2f}"
        )
        return result

    def process_batch(
        self,
        documents: List[Tuple[str, str]],
        tasks: Optional[List[NLPTask]] = None,
    ) -> List[NLPResult]:
        """Process multiple documents in batch."""
        return [
            self.process(doc_id, text, tasks)
            for doc_id, text in documents
        ]

    # ── Topic Classification ─────────────────────────────────────────────────

    def _classify_topics(self, text: str) -> Tuple[List[NLPTopic], Dict[str, float]]:
        """Classify text into financial topics using keyword matching."""
        scores: Dict[NLPTopic, float] = {}

        for topic, keywords in TOPIC_KEYWORDS.items():
            match_count = sum(1 for kw in keywords if kw in text)
            if match_count > 0:
                # Score based on match density
                scores[topic] = min(match_count / len(keywords) * 5, 1.0)

        # Sort by score, filter by threshold, limit
        sorted_topics = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        selected = [
            (topic, score)
            for topic, score in sorted_topics
            if score >= self.config.min_topic_confidence
        ][: self.config.max_topics]

        if not selected:
            return [NLPTopic.OTHER], {"other": 0.1}

        return (
            [t for t, _ in selected],
            {t.value: s for t, s in selected},
        )

    # ── Keyword Extraction ───────────────────────────────────────────────────

    def _extract_keywords(
        self, text: str
    ) -> Tuple[List[str], Dict[str, float]]:
        """Extract keywords using word frequency analysis."""
        # Tokenize
        words = re.findall(r"\b[a-z\u4e00-\u9fff]{2,}\b", text)

        # Count frequencies, filter stop words
        word_counts = Counter(
            w for w in words if w not in STOP_WORDS
        )

        total = sum(word_counts.values()) or 1
        max_count = max(word_counts.values()) or 1

        # Score as normalized frequency
        scored = {
            word: min(count / max_count, 1.0)
            for word, count in word_counts.most_common(self.config.max_keywords)
            if count / max_count >= self.config.min_keyword_score
        }

        return list(scored.keys()), scored

    # ── Summarization ────────────────────────────────────────────────────────

    def _summarize(self, text: str) -> str:
        """Extractive summarization: pick first sentences up to max length."""
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)

        if not sentences:
            return text[: self.config.max_summary_length]

        summary = ""
        for sent in sentences:
            if len(summary) + len(sent) > self.config.max_summary_length:
                break
            summary += sent + " "

        return summary.strip()

    # ── Direction Detection ──────────────────────────────────────────────────

    def _detect_direction(self, text: str) -> Tuple[str, float]:
        """Detect sentiment direction (positive/negative/neutral)."""
        words = set(re.findall(r"\b[a-z\u4e00-\u9fff]{2,}\b", text))

        positive_hits = len(words & POSITIVE_KEYWORDS)
        negative_hits = len(words & NEGATIVE_KEYWORDS)

        if positive_hits > negative_hits:
            confidence = min(
                (positive_hits - negative_hits) / max(positive_hits + negative_hits, 1),
                1.0,
            )
            return "positive", confidence
        elif negative_hits > positive_hits:
            confidence = min(
                (negative_hits - positive_hits) / max(positive_hits + negative_hits, 1),
                1.0,
            )
            return "negative", confidence
        else:
            return "neutral", 0.5

    # ── Confidence Computation ───────────────────────────────────────────────

    def _compute_confidence(self, result: NLPResult) -> float:
        """Compute overall confidence score."""
        scores = []

        if result.topic_scores:
            scores.append(max(result.topic_scores.values()))
        if result.direction_confidence > 0:
            scores.append(result.direction_confidence)
        if result.keyword_scores:
            scores.append(sum(result.keyword_scores.values()) / len(result.keyword_scores))

        return sum(scores) / len(scores) if scores else 0.1

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_results(
        self,
        document_id: Optional[str] = None,
        topic: Optional[NLPTopic] = None,
        direction: Optional[str] = None,
        limit: int = 100,
    ) -> List[NLPResult]:
        """Query NLP results with filters."""
        results = self._results

        if document_id:
            results = [r for r in results if r.document_id == document_id]
        if topic:
            results = [r for r in results if topic in r.topics]
        if direction:
            results = [r for r in results if r.direction == direction]

        return results[-limit:]

    def clear(self) -> None:
        """Clear all results."""
        self._results.clear()
