"""
Event Extraction Engine.

Extracts market-moving events from financial text:
- Earnings surprises
- Product launches
- M&A announcements
- Regulatory changes
- Supply chain events
- Capital expenditure changes
- Management changes
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class EventType(str, Enum):
    EARNINGS_SURPRISE = "earnings_surprise"
    EARNINGS_MISS = "earnings_miss"
    GUIDANCE_RAISED = "guidance_raised"
    GUIDANCE_LOWERED = "guidance_lowered"
    PRODUCT_LAUNCH = "product_launch"
    PRODUCT_RECALL = "product_recall"
    M_AND_A_ANNOUNCED = "merger_acquisition_announced"
    M_AND_A_COMPLETED = "merger_acquisition_completed"
    M_AND_A_TERMINATED = "merger_acquisition_terminated"
    REGULATION_NEW = "regulation_new"
    REGULATION_CHANGE = "regulation_change"
    REGULATION_FINE = "regulation_fine"
    SUPPLY_CHAIN_DISRUPTION = "supply_chain_disruption"
    SUPPLY_CHAIN_EXPANSION = "supply_chain_expansion"
    CAPEX_INCREASE = "capex_increase"
    CAPEX_DECREASE = "capex_decrease"
    MANAGEMENT_APPOINTMENT = "management_appointment"
    MANAGEMENT_RESIGNATION = "management_resignation"
    DIVIDEND_INCREASE = "dividend_increase"
    DIVIDEND_DECREASE = "dividend_decrease"
    BUYBACK_ANNOUNCED = "buyback_announced"
    IPO_ANNOUNCED = "ipo_announced"
    BANKRUPTCY = "bankruptcy"
    RESTRUCTURING = "restructuring"
    PARTNERSHIP = "partnership"
    PATENT_APPROVAL = "patent_approval"
    CLINICAL_TRIAL = "clinical_trial"
    FDA_APPROVAL = "fda_approval"
    MACRO_RATE_HIKE = "macro_rate_hike"
    MACRO_RATE_CUT = "macro_rate_cut"
    MACRO_DATA_RELEASE = "macro_data_release"
    GEOPOLITICAL_EVENT = "geopolitical_event"
    SECTOR_ROTATION = "sector_rotation"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    OTHER = "other"


class EventImpact(str, Enum):
    STRONG_POSITIVE = "strong_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    STRONG_NEGATIVE = "strong_negative"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class MarketEvent:
    """A market-moving event extracted from text."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.OTHER
    event_subtype: str = ""

    # Source
    document_id: str = ""
    source: str = ""

    # Primary entity
    primary_entity: str = ""  # company name or ticker
    entity_type: str = "company"

    # Impact
    impact: EventImpact = EventImpact.NEUTRAL
    impact_score: float = 0.0  # -1.0 to 1.0
    confidence: float = 0.0

    # Details
    title: str = ""
    description: str = ""
    extracted_text: str = ""  # the specific text that triggered extraction
    keywords: List[str] = field(default_factory=list)

    # Affected entities
    affected_symbols: List[str] = field(default_factory=list)
    affected_sectors: List[str] = field(default_factory=list)
    affected_industries: List[str] = field(default_factory=list)

    # Propagation (filled by knowledge graph)
    related_entities: List[str] = field(default_factory=list)
    propagation_path: List[str] = field(default_factory=list)

    # Quantification
    magnitude: float = 0.0  # estimated magnitude of impact
    duration_hint: str = ""  # short_term, medium_term, long_term

    # Timestamps
    event_date: Optional[datetime] = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Alpha potential
    alpha_potential: float = 0.0  # 0-1, how actionable is this event

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "event_subtype": self.event_subtype,
            "document_id": self.document_id,
            "source": self.source,
            "primary_entity": self.primary_entity,
            "impact": self.impact.value,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "affected_symbols": self.affected_symbols,
            "affected_sectors": self.affected_sectors,
            "affected_industries": self.affected_industries,
            "related_entities": self.related_entities,
            "alpha_potential": self.alpha_potential,
            "event_date": self.event_date.isoformat() if self.event_date else None,
        }


@dataclass
class EventExtractionResult:
    """Result of event extraction from a document."""

    document_id: str = ""
    events: List[MarketEvent] = field(default_factory=list)
    event_count: int = 0
    primary_event: Optional[MarketEvent] = None
    extraction_time_ms: float = 0.0


@dataclass
class EventConfig:
    """Configuration for event extraction engine."""

    # Event types to extract
    enabled_event_types: Set[EventType] = field(default_factory=lambda: set(EventType))

    # Impact thresholds
    min_confidence: float = 0.3
    min_impact_score: float = 0.1

    # Filtering
    max_events_per_doc: int = 5

    # Rule-based extraction
    use_pattern_rules: bool = True
    use_keyword_rules: bool = True


# ── Event Rule Definitions ───────────────────────────────────────────────────

# Pattern-based rules: (regex_pattern, EventType, impact_score)
EVENT_PATTERNS: List[Tuple[str, EventType, float]] = [
    # Earnings
    (r"(beat|exceeded?|surpassed?)\s+(?:analysts?'?\s*)?(?:earnings\s*)?estimates?", EventType.EARNINGS_SURPRISE, 0.7),
    (r"(missed?|fell\s+short\s+of|below)\s+(?:analysts?'?\s*)?(?:earnings\s*)?estimates?", EventType.EARNINGS_MISS, -0.7),
    (r"raised?\s+(?:its?\s+)?(?:full[.\-\s]*year|FY\d*|quarterly|Q\s*\d)\s*(?:\w+\s+)*(?:revenue|earnings|profit|EPS|guidance)", EventType.GUIDANCE_RAISED, 0.6),
    (r"(lowered?|cut|reduced?)\s+(?:its?\s+)?(?:full[.\-\s]*year|FY\d*|quarterly|Q\s*\d)\s*(?:\w+\s+)*(?:revenue|earnings|profit|EPS|guidance)", EventType.GUIDANCE_LOWERED, -0.6),

    # M&A
    (r"(?:announced?|agreed?\s+to)\s+.+?\s(?:acquire|acquisition|merge|merger|buyout|takeover)", EventType.M_AND_A_ANNOUNCED, 0.5),
    (r"(?:completed?|closed?|finalized?)\s+.+?\s(?:acquisition|merger|takeover)", EventType.M_AND_A_COMPLETED, 0.3),
    (r"(?:terminated?|abandoned?|called\s+off)\s+.+?\s(?:acquisition|merger|deal)", EventType.M_AND_A_TERMINATED, -0.3),

    # Product
    (r"(?:announced?|launched?|unveiled?|released?)\s+(?:a\s+)?(?:new\s+)?\w*\s*(?:product|model|version|generation|chip|device)", EventType.PRODUCT_LAUNCH, 0.5),
    (r"(?:recalled?|recall)\s+(?:of\s+)?(?:product|model|device|vehicle)", EventType.PRODUCT_RECALL, -0.6),

    # Regulation
    (r"(?:SEC|FTC|DOJ|regulator)\s+(?:investigation|fine|penalty|lawsuit|charged?)", EventType.REGULATION_FINE, -0.7),
    (r"(?:approved?|cleared?|authorized?)\s+(?:by\s+)?(?:FDA|regulator|SEC)", EventType.REGULATION_NEW, 0.4),

    # Supply Chain
    (r"supply\s+chain\s+(?:disruption|shortage|bottleneck|issue|constraint)", EventType.SUPPLY_CHAIN_DISRUPTION, -0.5),
    (r"(?:expanded?|expand|scaling?)\s+(?:production|manufacturing|capacity|supply\s+chain)", EventType.SUPPLY_CHAIN_EXPANSION, 0.4),

    # CAPEX
    (r"(?:increased?|boosted?|raised?|expanded?)\s+(?:its?\s+)?(?:capital\s+expenditure|capex|investment|spending|budget)", EventType.CAPEX_INCREASE, 0.4),
    (r"(?:reduced?|cut|lowered?|decreased?)\s+(?:its?\s+)?(?:capital\s+expenditure|capex|investment|spending)", EventType.CAPEX_DECREASE, -0.3),

    # Management
    (r"(?:appointed?|named?|hired?)\s+(?:as\s+)?(?:new\s+)?(?:CEO|CFO|COO|CTO|president|director)", EventType.MANAGEMENT_APPOINTMENT, 0.1),
    (r"(?:resigned?|stepped?\s+down|depart(?:ed|ure)|left)\s+(?:as\s+)?(?:CEO|CFO|COO|CTO|president|director)", EventType.MANAGEMENT_RESIGNATION, -0.3),

    # Dividend/Buyback
    (r"(?:increased?|raised?|boosted?)\s+.+?\s(?:dividend|payout)", EventType.DIVIDEND_INCREASE, 0.4),
    (r"(?:reduced?|cut|suspended?)\s+.+?\s(?:dividend|payout)", EventType.DIVIDEND_DECREASE, -0.4),
    (r"(?:announced?|authorized?)\s+.+?\s(?:share|stock)\s+(?:buyback|repurchase)", EventType.BUYBACK_ANNOUNCED, 0.3),

    # Other
    (r"(?:filed\s+for|declared?)\s+(?:bankruptcy|chapter\s+11)", EventType.BANKRUPTCY, -0.9),
    (r"(?:announced?|formed?)\s+(?:a\s+)?(?:strategic\s+)?partnership", EventType.PARTNERSHIP, 0.3),
    (r"(?:FDA|EMA)\s+(?:approved?|cleared?|authorized?)", EventType.FDA_APPROVAL, 0.7),
    (r"(?:phase\s+[123])\s+(?:clinical\s+)?trial\s+(?:results?|data|readout)", EventType.CLINICAL_TRIAL, 0.3),

    # Macro
    (r"(?:Fed|Federal\s+Reserve|central\s+bank)\s+(?:raised?|hiked?)\s+(?:interest\s+)?rates?", EventType.MACRO_RATE_HIKE, -0.4),
    (r"(?:Fed|Federal\s+Reserve|central\s+bank)\s+(?:cut|lowered?|reduced?)\s+(?:interest\s+)?rates?", EventType.MACRO_RATE_CUT, 0.4),

    # Analyst
    (r"(?:analyst|broker|firm)\s+(?:upgraded?|raised?\s+target|initiated?\s+coverage\s+with\s+buy)", EventType.ANALYST_UPGRADE, 0.5),
    (r"(?:analyst|broker|firm)\s+(?:downgraded?|lowered?\s+target|initiated?\s+coverage\s+with\s+sell)", EventType.ANALYST_DOWNGRADE, -0.5),
]


# ── Event Engine ─────────────────────────────────────────────────────────────

class EventEngine:
    """
    Event extraction engine for financial text.

    Uses pattern matching and keyword rules to identify
    market-moving events and assess their impact.
    """

    def __init__(self, config: Optional[EventConfig] = None):
        self.config = config or EventConfig()
        self._events: List[MarketEvent] = []
        self._compiled_patterns: List[Tuple[re.Pattern, EventType, float]] = [
            (re.compile(p, re.IGNORECASE), et, score)
            for p, et, score in EVENT_PATTERNS
        ]

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract(
        self,
        document_id: str,
        text: str,
        primary_entity: str = "",
        affected_symbols: Optional[List[str]] = None,
        source: str = "",
    ) -> EventExtractionResult:
        """
        Extract events from document text.

        Args:
            document_id: Document identifier.
            text: Full document text.
            primary_entity: Primary company/entity name.
            affected_symbols: Known affected symbols.
            source: Data source.

        Returns:
            EventExtractionResult with all detected events.
        """
        import time
        start = time.time()

        text_lower = text.lower()
        events: List[MarketEvent] = []

        # Pattern-based extraction
        if self.config.use_pattern_rules:
            events.extend(self._extract_by_patterns(
                document_id, text_lower, text, primary_entity, affected_symbols, source
            ))

        # Keyword-based extraction (complementary)
        if self.config.use_keyword_rules:
            events.extend(self._extract_by_keywords(
                document_id, text_lower, text, primary_entity, affected_symbols, source
            ))

        # Deduplicate and sort
        events = self._deduplicate(events)
        events.sort(key=lambda e: abs(e.impact_score), reverse=True)
        events = events[: self.config.max_events_per_doc]

        # Store
        self._events.extend(events)

        primary = events[0] if events else None
        elapsed = (time.time() - start) * 1000

        return EventExtractionResult(
            document_id=document_id,
            events=events,
            event_count=len(events),
            primary_event=primary,
            extraction_time_ms=elapsed,
        )

    def _extract_by_patterns(
        self,
        document_id: str,
        text_lower: str,
        text: str,
        primary_entity: str,
        affected_symbols: Optional[List[str]],
        source: str,
    ) -> List[MarketEvent]:
        """Extract events using regex pattern rules."""
        events = []

        for pattern, event_type, base_impact in self._compiled_patterns:
            # Check if event type is enabled
            if self.config.enabled_event_types:
                if event_type not in self.config.enabled_event_types:
                    continue

            match = pattern.search(text_lower)
            if not match:
                continue

            # Get matched text and surrounding context
            start, end = match.start(), match.end()
            context_start = max(0, start - 100)
            context_end = min(len(text), end + 100)
            matched_text = text[context_start:context_end]

            # Determine impact
            impact = self._impact_from_score(base_impact)

            # Compute confidence based on pattern specificity
            confidence = min(0.5 + (len(match.group()) / 50), 0.9)

            event = MarketEvent(
                event_type=event_type,
                document_id=document_id,
                source=source,
                primary_entity=primary_entity,
                impact=impact,
                impact_score=base_impact,
                confidence=confidence,
                description=matched_text.strip(),
                extracted_text=match.group(),
                affected_symbols=affected_symbols or [],
                alpha_potential=abs(base_impact) * confidence,
            )
            events.append(event)

        return events

    def _extract_by_keywords(
        self,
        document_id: str,
        text_lower: str,
        text: str,
        primary_entity: str,
        affected_symbols: Optional[List[str]],
        source: str,
    ) -> List[MarketEvent]:
        """Extract events using keyword rules (fallback)."""
        events = []

        # Earnings surprise keywords
        if "beat expectations" in text_lower or "record revenue" in text_lower:
            if self._is_type_enabled(EventType.EARNINGS_SURPRISE):
                events.append(self._make_event(
                    document_id, EventType.EARNINGS_SURPRISE, 0.6,
                    primary_entity, affected_symbols, source,
                ))

        # M&A keywords
        if "definitive agreement" in text_lower and "acquire" in text_lower:
            if self._is_type_enabled(EventType.M_AND_A_ANNOUNCED):
                events.append(self._make_event(
                    document_id, EventType.M_AND_A_ANNOUNCED, 0.5,
                    primary_entity, affected_symbols, source,
                ))

        # Restructuring
        if "restructuring" in text_lower and ("layoff" in text_lower or "cost reduction" in text_lower):
            if self._is_type_enabled(EventType.RESTRUCTURING):
                events.append(self._make_event(
                    document_id, EventType.RESTRUCTURING, -0.3,
                    primary_entity, affected_symbols, source,
                ))

        # Geopolitical
        if any(w in text_lower for w in ["sanction", "tariff", "trade war", "embargo"]):
            if self._is_type_enabled(EventType.GEOPOLITICAL_EVENT):
                impact = -0.5 if "sanction" in text_lower or "tariff" in text_lower else -0.3
                events.append(self._make_event(
                    document_id, EventType.GEOPOLITICAL_EVENT, impact,
                    primary_entity, affected_symbols, source,
                ))

        # Macro data release
        if any(w in text_lower for w in ["gdp report", "cpi data", "jobs report", "pmi"]):
            if self._is_type_enabled(EventType.MACRO_DATA_RELEASE):
                events.append(self._make_event(
                    document_id, EventType.MACRO_DATA_RELEASE, 0.0,
                    primary_entity, affected_symbols, source,
                ))

        return events

    def _make_event(
        self,
        document_id: str,
        event_type: EventType,
        impact_score: float,
        primary_entity: str,
        affected_symbols: Optional[List[str]],
        source: str,
    ) -> MarketEvent:
        return MarketEvent(
            event_type=event_type,
            document_id=document_id,
            source=source,
            primary_entity=primary_entity,
            impact=self._impact_from_score(impact_score),
            impact_score=impact_score,
            confidence=0.5,
            affected_symbols=affected_symbols or [],
            alpha_potential=abs(impact_score) * 0.5,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _impact_from_score(self, score: float) -> EventImpact:
        """Convert numeric score to EventImpact enum."""
        if score >= 0.6:
            return EventImpact.STRONG_POSITIVE
        elif score > 0.1:
            return EventImpact.POSITIVE
        elif score >= -0.1:
            return EventImpact.NEUTRAL
        elif score > -0.6:
            return EventImpact.NEGATIVE
        else:
            return EventImpact.STRONG_NEGATIVE

    def _is_type_enabled(self, event_type: EventType) -> bool:
        """Check if an event type is enabled."""
        if not self.config.enabled_event_types:
            return True
        return event_type in self.config.enabled_event_types

    def _deduplicate(self, events: List[MarketEvent]) -> List[MarketEvent]:
        """Remove duplicate events."""
        seen: Set[Tuple[EventType, str]] = set()
        unique = []
        for event in events:
            key = (event.event_type, event.primary_entity)
            if key not in seen:
                seen.add(key)
                unique.append(event)
        return unique

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        entity: Optional[str] = None,
        impact: Optional[EventImpact] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[MarketEvent]:
        """Query events with filters."""
        results = self._events

        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if entity:
            entity_lower = entity.lower()
            results = [
                e for e in results
                if entity_lower in e.primary_entity.lower()
                or entity_lower in [s.lower() for s in e.affected_symbols]
            ]
        if impact:
            results = [e for e in results if e.impact == impact]
        if min_confidence > 0:
            results = [e for e in results if e.confidence >= min_confidence]

        return results[-limit:]

    def get_high_impact_events(self, limit: int = 20) -> List[MarketEvent]:
        """Get events with highest absolute impact."""
        sorted_events = sorted(
            self._events,
            key=lambda e: abs(e.impact_score),
            reverse=True,
        )
        return sorted_events[:limit]

    def get_events_by_symbol(self, symbol: str, limit: int = 50) -> List[MarketEvent]:
        """Get all events affecting a symbol."""
        symbol_upper = symbol.upper()
        return [
            e for e in self._events
            if symbol_upper in [s.upper() for s in e.affected_symbols]
        ][-limit:]

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
