"""
Entity Extraction Engine.

Extracts financial entities from text:
- Companies, products, industries, people
- Ticker symbols and ISINs
- Named entity recognition (NER)
- Entity linking and disambiguation
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class EntityType(str, Enum):
    COMPANY = "company"
    TICKER = "ticker"
    PRODUCT = "product"
    INDUSTRY = "industry"
    SECTOR = "sector"
    PERSON = "person"
    LOCATION = "location"
    EVENT = "event"
    INDEX = "index"
    CURRENCY = "currency"
    COMMODITY = "commodity"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    REGULATION = "regulation"
    OTHER = "other"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class EntityMention:
    """A specific mention of an entity in text."""

    entity_name: str
    entity_type: EntityType
    start_pos: int = 0
    end_pos: int = 0
    confidence: float = 0.0
    context: str = ""  # surrounding text snippet


@dataclass
class ExtractedEntity:
    """An extracted entity with all its mentions and metadata."""

    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    canonical_name: str = ""
    entity_type: EntityType = EntityType.OTHER

    # Mentions
    mentions: List[EntityMention] = field(default_factory=list)
    mention_count: int = 0

    # Relationships
    related_entities: List[str] = field(default_factory=list)
    parent_entity: Optional[str] = None

    # Attributes
    aliases: List[str] = field(default_factory=list)
    ticker: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

    # Scores
    relevance_score: float = 0.0
    confidence: float = 0.0

    # Source
    document_id: str = ""
    source: str = ""

    # Timestamp
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value,
            "mention_count": self.mention_count,
            "related_entities": self.related_entities,
            "aliases": self.aliases,
            "ticker": self.ticker,
            "sector": self.sector,
            "industry": self.industry,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "document_id": self.document_id,
        }


@dataclass
class ExtractionConfig:
    """Configuration for entity extraction."""

    # Entity types to extract
    enabled_types: Set[EntityType] = field(default_factory=lambda: set(EntityType))

    # Minimum confidence
    min_confidence: float = 0.1

    # Deduplication
    dedup_threshold: float = 0.85  # similarity threshold for merging entities

    # Context window size (characters around mention)
    context_window: int = 100

    # Maximum entities per document
    max_entities_per_doc: int = 50


# ── Entity Knowledge Base (extensible) ───────────────────────────────────────

# Major company name → ticker mapping
COMPANY_TICKER_MAP: Dict[str, str] = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
    "alphabet": "GOOGL", "amazon": "AMZN", "nvidia": "NVDA",
    "tesla": "TSLA", "meta": "META", "facebook": "META",
    "netflix": "NFLX", "intel": "INTC", "amd": "AMD",
    "broadcom": "AVGO", "qualcomm": "QCOM", "micron": "MU",
    "taiwan semiconductor": "TSM", "tsmc": "TSM",
    "samsung": "005930.KS", "sk hynix": "000660.KS",
    "jpmorgan": "JPM", "goldman sachs": "GS", "morgan stanley": "MS",
    "berkshire hathaway": "BRK.A", "bank of america": "BAC",
    "johnson & johnson": "JNJ", "pfizer": "PFE", "moderna": "MRNA",
    "exxon": "XOM", "chevron": "CVX", "shell": "SHEL",
    "walmart": "WMT", "costco": "COST", "home depot": "HD",
    "caterpillar": "CAT", "boeing": "BA", "lockheed martin": "LMT",
    "disney": "DIS", "comcast": "CMCSA", "at&t": "T",
    "coca-cola": "KO", "pepsico": "PEP", "mcdonalds": "MCD",
    "visa": "V", "mastercard": "MA", "paypal": "PYPL",
    "salesforce": "CRM", "adobe": "ADBE", "oracle": "ORCL",
    "cisco": "CSCO", "ibm": "IBM", "accenture": "ACN",
    "alibaba": "BABA", "tencent": "0700.HK", "byd": "002594.SZ",
    "toyota": "TM", "sony": "SONY", "nintendo": "NTDOY",
    "asml": "ASML", "sap": "SAP", "siemens": "SIEGY",
}

# Product-to-company mapping
PRODUCT_COMPANY_MAP: Dict[str, str] = {
    "iphone": "AAPL", "ipad": "AAPL", "macbook": "AAPL",
    "windows": "MSFT", "azure": "MSFT", "office 365": "MSFT",
    "aws": "AMZN", "alexa": "AMZN",
    "geforce": "NVDA", "cuda": "NVDA", "blackwell": "NVDA",
    "tesla model": "TSLA", "cybertruck": "TSLA",
    "android": "GOOGL", "chrome": "GOOGL", "google cloud": "GOOGL",
    "ryzen": "AMD", "epyc": "AMD",
    "core i": "INTC", "xeon": "INTC",
}

# Industry/sector keywords
INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "semiconductors": ["semiconductor", "chip", "wafer", "foundry", "fab"],
    "ai_ml": ["artificial intelligence", "machine learning", "deep learning", "llm"],
    "cloud_computing": ["cloud", "saas", "paas", "iaas", "data center"],
    "electric_vehicles": ["electric vehicle", "ev", "battery", "autonomous driving"],
    "fintech": ["fintech", "payment", "digital banking", "crypto"],
    "biotech": ["biotech", "pharmaceutical", "drug", "clinical trial", "fda"],
    "renewable_energy": ["solar", "wind", "renewable", "clean energy", "hydrogen"],
    "cybersecurity": ["cybersecurity", "firewall", "encryption", "zero trust"],
    "robotics": ["robotics", "automation", "rpa"],
    "quantum": ["quantum computing", "quantum"],
}


# ── Entity Extractor ─────────────────────────────────────────────────────────

class EntityExtractor:
    """
    Financial entity extraction engine.

    Extracts companies, products, industries, people, and other
    financial entities from text using pattern matching and
    knowledge base lookups.
    """

    # Ticker pattern: $AAPL or (NASDAQ: AAPL)
    TICKER_PATTERN = re.compile(
        r'\$([A-Z]{1,5})\b|\(([A-Z]+):\s*([A-Z]{1,5})\)'
    )

    # Person name pattern (simplified)
    PERSON_PATTERN = re.compile(
        r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})\b'
    )

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self._entities: Dict[str, ExtractedEntity] = {}
        self._entity_index: Dict[str, List[str]] = defaultdict(list)

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract(
        self,
        document_id: str,
        text: str,
        symbols_hint: Optional[List[str]] = None,
    ) -> List[ExtractedEntity]:
        """
        Extract all entities from a text document.

        Args:
            document_id: Document identifier.
            text: Raw text to extract from.
            symbols_hint: Known related symbols to boost matching.

        Returns:
            List of extracted entities.
        """
        text_lower = text.lower()
        extracted: List[ExtractedEntity] = []

        # Extract by type
        if EntityType.COMPANY in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_companies(text_lower, document_id))

        if EntityType.TICKER in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_tickers(text, document_id))

        if EntityType.PRODUCT in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_products(text_lower, document_id))

        if EntityType.INDUSTRY in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_industries(text_lower, document_id))

        if EntityType.PERSON in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_people(text, document_id))

        if EntityType.SECTOR in self.config.enabled_types or not self.config.enabled_types:
            extracted.extend(self._extract_sectors(text_lower, document_id))

        # Deduplicate and merge
        merged = self._merge_entities(extracted)

        # Boost relevance with symbol hints
        if symbols_hint:
            merged = self._boost_relevance(merged, symbols_hint)

        # Limit per document
        merged.sort(key=lambda e: e.relevance_score, reverse=True)
        merged = merged[: self.config.max_entities_per_doc]

        # Index
        for entity in merged:
            self._index_entity(entity)

        return merged

    # ── Company Extraction ───────────────────────────────────────────────────

    def _extract_companies(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()

        for company_name, ticker in COMPANY_TICKER_MAP.items():
            if company_name in text and company_name not in seen:
                seen.add(company_name)
                # Find mentions
                mentions = self._find_mentions(text, company_name, EntityType.COMPANY)

                entity = ExtractedEntity(
                    name=company_name.title(),
                    canonical_name=company_name.title(),
                    entity_type=EntityType.COMPANY,
                    mentions=mentions,
                    mention_count=len(mentions),
                    ticker=ticker,
                    document_id=document_id,
                    relevance_score=len(mentions) * 0.2,
                    confidence=0.8,
                )
                entities.append(entity)

        return entities

    # ── Ticker Extraction ────────────────────────────────────────────────────

    def _extract_tickers(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()

        for match in self.TICKER_PATTERN.finditer(text):
            ticker = match.group(1) or match.group(3)
            if ticker and ticker not in seen:
                seen.add(ticker)
                start, end = match.start(), match.end()

                # Find company name for this ticker
                company_name = ""
                for name, tk in COMPANY_TICKER_MAP.items():
                    if tk == ticker:
                        company_name = name.title()
                        break

                entity = ExtractedEntity(
                    name=ticker,
                    canonical_name=company_name or ticker,
                    entity_type=EntityType.TICKER,
                    mentions=[
                        EntityMention(
                            entity_name=ticker,
                            entity_type=EntityType.TICKER,
                            start_pos=start,
                            end_pos=end,
                            confidence=0.95,
                            context=text[max(0, start - 40):end + 40],
                        )
                    ],
                    mention_count=1,
                    ticker=ticker,
                    document_id=document_id,
                    confidence=0.95,
                )
                entities.append(entity)

        return entities

    # ── Product Extraction ───────────────────────────────────────────────────

    def _extract_products(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()

        for product_name, company_ticker in PRODUCT_COMPANY_MAP.items():
            if product_name in text and product_name not in seen:
                seen.add(product_name)
                mentions = self._find_mentions(text, product_name, EntityType.PRODUCT)

                entity = ExtractedEntity(
                    name=product_name.title(),
                    canonical_name=product_name.title(),
                    entity_type=EntityType.PRODUCT,
                    mentions=mentions,
                    mention_count=len(mentions),
                    related_entities=[company_ticker],
                    document_id=document_id,
                    relevance_score=len(mentions) * 0.15,
                    confidence=0.7,
                )
                entities.append(entity)

        return entities

    # ── Industry Extraction ──────────────────────────────────────────────────

    def _extract_industries(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()

        for industry, keywords in INDUSTRY_KEYWORDS.items():
            for kw in keywords:
                if kw in text and kw not in seen:
                    seen.add(kw)
                    entity = ExtractedEntity(
                        name=kw,
                        canonical_name=industry.replace("_", " ").title(),
                        entity_type=EntityType.INDUSTRY,
                        mentions=[
                            EntityMention(
                                entity_name=kw,
                                entity_type=EntityType.INDUSTRY,
                                confidence=0.6,
                                context="",
                            )
                        ],
                        mention_count=1,
                        industry=industry,
                        document_id=document_id,
                        relevance_score=0.3,
                        confidence=0.6,
                    )
                    entities.append(entity)

        return entities

    # ── Person Extraction ────────────────────────────────────────────────────

    COMMON_PERSON_NAMES = {
        "jensen huang", "tim cook", "satya nadella", "elon musk",
        "mark zuckerberg", "andy jassy", "sundar pichai",
        "jamie dimon", "warren buffett", "jerome powell",
        "lisa su", "pat gelsinger", "cristiano amon",
        "mary barra", "brian moynihan", "david solomon",
        "albert bourla", "stephane bancel",
    }

    def _extract_people(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()
        text_lower = text.lower()

        for name in self.COMMON_PERSON_NAMES:
            if name in text_lower and name not in seen:
                seen.add(name)
                entity = ExtractedEntity(
                    name=name.title(),
                    canonical_name=name.title(),
                    entity_type=EntityType.PERSON,
                    mentions=[
                        EntityMention(
                            entity_name=name.title(),
                            entity_type=EntityType.PERSON,
                            confidence=0.85,
                        )
                    ],
                    mention_count=1,
                    document_id=document_id,
                    relevance_score=0.3,
                    confidence=0.85,
                )
                entities.append(entity)

        return entities

    # ── Sector Extraction ────────────────────────────────────────────────────

    SECTORS = {
        "technology": ["technology", "tech", "software", "hardware", "it"],
        "financials": ["financial", "bank", "insurance", "fintech"],
        "healthcare": ["healthcare", "pharma", "biotech", "medical"],
        "energy": ["energy", "oil", "gas", "renewable energy"],
        "consumer": ["consumer", "retail", "e-commerce"],
        "industrial": ["industrial", "manufacturing", "aerospace"],
        "materials": ["materials", "mining", "chemicals"],
        "real_estate": ["real estate", "reit", "property"],
        "utilities": ["utilities", "electric", "water"],
        "communication": ["telecom", "media", "entertainment"],
    }

    def _extract_sectors(
        self, text: str, document_id: str
    ) -> List[ExtractedEntity]:
        entities = []
        seen = set()

        for sector, keywords in self.SECTORS.items():
            for kw in keywords:
                if kw in text and kw not in seen:
                    seen.add(kw)
                    entity = ExtractedEntity(
                        name=sector.title(),
                        canonical_name=sector.title(),
                        entity_type=EntityType.SECTOR,
                        sector=sector,
                        document_id=document_id,
                        relevance_score=0.2,
                        confidence=0.5,
                    )
                    entities.append(entity)
                    break  # One per sector

        return entities

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _find_mentions(
        self, text: str, term: str, entity_type: EntityType
    ) -> List[EntityMention]:
        """Find all mentions of a term in text."""
        mentions = []
        idx = 0
        term_len = len(term)
        while True:
            idx = text.find(term, idx)
            if idx == -1:
                break
            context = text[max(0, idx - self.config.context_window):idx + term_len + self.config.context_window]
            mentions.append(EntityMention(
                entity_name=term,
                entity_type=entity_type,
                start_pos=idx,
                end_pos=idx + term_len,
                confidence=0.8,
                context=context,
            ))
            idx += term_len
        return mentions

    def _merge_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Merge duplicate/similar entities."""
        merged: Dict[str, ExtractedEntity] = {}

        for entity in entities:
            key = entity.canonical_name.lower() or entity.name.lower()
            if key in merged:
                existing = merged[key]
                existing.mentions.extend(entity.mentions)
                existing.mention_count += entity.mention_count
                existing.relevance_score = max(
                    existing.relevance_score, entity.relevance_score
                )
                existing.related_entities = list(
                    set(existing.related_entities + entity.related_entities)
                )
            else:
                merged[key] = entity

        return list(merged.values())

    def _boost_relevance(
        self, entities: List[ExtractedEntity], symbols: List[str]
    ) -> List[ExtractedEntity]:
        """Boost relevance of entities matching known symbols."""
        symbol_set = set(s.upper() for s in symbols)
        for entity in entities:
            if entity.ticker and entity.ticker.upper() in symbol_set:
                entity.relevance_score = min(entity.relevance_score + 0.3, 1.0)
        return entities

    def _index_entity(self, entity: ExtractedEntity) -> None:
        """Index entity for lookup."""
        self._entities[entity.entity_id] = entity
        key = entity.canonical_name.lower() or entity.name.lower()
        if entity.entity_id not in self._entity_index.get(key, []):
            self._entity_index.setdefault(key, []).append(entity.entity_id)

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_entity(self, entity_id: str) -> Optional[ExtractedEntity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)

    def find_entity(self, name: str) -> Optional[ExtractedEntity]:
        """Find entity by name."""
        key = name.lower()
        ids = self._entity_index.get(key, [])
        if ids:
            return self._entities.get(ids[0])
        return None

    def get_by_type(
        self, entity_type: EntityType, limit: int = 100
    ) -> List[ExtractedEntity]:
        """Get entities by type."""
        results = [
            e for e in self._entities.values()
            if e.entity_type == entity_type
        ]
        results.sort(key=lambda e: e.relevance_score, reverse=True)
        return results[:limit]

    def get_by_ticker(self, ticker: str) -> Optional[ExtractedEntity]:
        """Get entity by ticker symbol."""
        ticker_upper = ticker.upper()
        for entity in self._entities.values():
            if entity.ticker and entity.ticker.upper() == ticker_upper:
                return entity
        return None

    def clear(self) -> None:
        """Clear all extracted entities."""
        self._entities.clear()
        self._entity_index.clear()



