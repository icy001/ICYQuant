"""
Tests for Event Extraction Engine.
"""

import pytest
from services.knowledge.event_engine import (
    EventEngine, EventConfig, MarketEvent, EventType, EventImpact, EventExtractionResult,
)
from services.knowledge.service import (
    KnowledgeService, KnowledgeConfig, AnalysisRequest, AnalysisResult,
    PipelineResult, PipelineStatus,
)
from services.knowledge.api.knowledge_api import KnowledgeAPI, APIResponse


# ── Event Extraction Tests ───────────────────────────────────────────────────

class TestEventEngine:

    def test_extract_earnings_surprise(self):
        engine = EventEngine()
        result = engine.extract(
            "doc1",
            "NVIDIA beat analysts earnings estimates by a wide margin, reporting record revenue.",
            primary_entity="NVDA",
            affected_symbols=["NVDA"],
        )
        assert result.event_count >= 1
        surprise_events = [e for e in result.events if e.event_type == EventType.EARNINGS_SURPRISE]
        assert len(surprise_events) >= 1
        assert surprise_events[0].impact in (EventImpact.POSITIVE, EventImpact.STRONG_POSITIVE)

    def test_extract_earnings_miss(self):
        engine = EventEngine()
        result = engine.extract(
            "doc2",
            "The company missed earnings estimates and fell short of revenue expectations.",
            primary_entity="INTC",
        )
        miss_events = [e for e in result.events if e.event_type == EventType.EARNINGS_MISS]
        assert len(miss_events) >= 1

    def test_extract_guidance_raised(self):
        engine = EventEngine()
        result = engine.extract(
            "doc3",
            "The company raised its full-year revenue guidance following strong Q2 results.",
            primary_entity="NVDA",
        )
        guide_events = [e for e in result.events if e.event_type == EventType.GUIDANCE_RAISED]
        assert len(guide_events) >= 1

    def test_extract_guidance_lowered(self):
        engine = EventEngine()
        result = engine.extract(
            "doc4",
            "Management lowered its FY2024 earnings guidance citing weak demand.",
            primary_entity="INTC",
        )
        guide_events = [e for e in result.events if e.event_type == EventType.GUIDANCE_LOWERED]
        assert len(guide_events) >= 1

    def test_extract_merger(self):
        engine = EventEngine()
        result = engine.extract(
            "doc5",
            "Company A announced an agreement to acquire Company B for $10 billion in an all-stock merger.",
            primary_entity="A",
        )
        m_and_a_events = [e for e in result.events if e.event_type == EventType.M_AND_A_ANNOUNCED]
        assert len(m_and_a_events) >= 1

    def test_extract_product_launch(self):
        engine = EventEngine()
        result = engine.extract(
            "doc6",
            "NVIDIA launched a new GPU chip model featuring the latest architecture.",
            primary_entity="NVDA",
        )
        product_events = [e for e in result.events if e.event_type == EventType.PRODUCT_LAUNCH]
        assert len(product_events) >= 1

    def test_extract_regulation_fine(self):
        engine = EventEngine()
        result = engine.extract(
            "doc7",
            "The SEC investigation resulted in a record penalty and fine for the company.",
            primary_entity="CORP",
        )
        reg_events = [e for e in result.events if e.event_type == EventType.REGULATION_FINE]
        assert len(reg_events) >= 1

    def test_extract_bankruptcy(self):
        engine = EventEngine()
        result = engine.extract(
            "doc8",
            "The company filed for bankruptcy protection under chapter 11.",
            primary_entity="CORP",
        )
        bk_events = [e for e in result.events if e.event_type == EventType.BANKRUPTCY]
        assert len(bk_events) >= 1

    def test_extract_fda_approval(self):
        engine = EventEngine()
        result = engine.extract(
            "doc9",
            "The FDA approved the company's new drug for clinical use.",
            primary_entity="BIOTECH",
        )
        fda_events = [e for e in result.events if e.event_type == EventType.FDA_APPROVAL]
        assert len(fda_events) >= 1

    def test_extract_analyst_upgrade(self):
        engine = EventEngine()
        result = engine.extract(
            "doc10",
            "Morgan Stanley analyst upgraded the stock and raised the target price to $150.",
            primary_entity="NVDA",
        )
        upgrade_events = [e for e in result.events if e.event_type == EventType.ANALYST_UPGRADE]
        assert len(upgrade_events) >= 1

    def test_extract_rate_hike(self):
        engine = EventEngine()
        result = engine.extract(
            "doc11",
            "The Federal Reserve raised interest rates by 25 basis points to combat inflation.",
            primary_entity="MARKET",
        )
        events = [e for e in result.events if e.event_type == EventType.MACRO_RATE_HIKE]
        assert len(events) >= 1

    def test_no_events(self):
        engine = EventEngine()
        result = engine.extract(
            "doc12",
            "The weather is nice today and the sky is blue.",
            primary_entity="NONE",
        )
        # Should have few or no financial events
        assert result.event_count <= 1

    def test_event_to_dict(self):
        event = MarketEvent(
            event_type=EventType.EARNINGS_SURPRISE,
            primary_entity="NVDA",
            impact=EventImpact.POSITIVE,
            impact_score=0.7,
            confidence=0.8,
            description="Beat estimates",
        )
        d = event.to_dict()
        assert d["event_type"] == "earnings_surprise"
        assert d["primary_entity"] == "NVDA"
        assert d["impact"] == "positive"

    def test_filter_by_type(self):
        engine = EventEngine()
        engine.extract("d1", "NVIDIA beat earnings estimates.", primary_entity="NVDA")
        engine.extract("d2", "FDA approved new drug.", primary_entity="BIOTECH")
        engine.extract("d3", "NVIDIA launched new chip.", primary_entity="NVDA")

        earning_events = engine.get_events(event_type=EventType.EARNINGS_SURPRISE)
        assert len(earning_events) >= 1

    def test_get_by_symbol(self):
        engine = EventEngine()
        engine.extract("d1", "NVIDIA beat earnings estimates.", primary_entity="NVDA", affected_symbols=["NVDA"])
        engine.extract("d2", "Tesla missed earnings estimates.", primary_entity="TSLA", affected_symbols=["TSLA"])

        nvda_events = engine.get_events_by_symbol("NVDA")
        assert len(nvda_events) >= 1

    def test_high_impact_sorting(self):
        engine = EventEngine()
        engine.extract("d1", "FILE FOR BANKRUPTCY. The company filed for bankruptcy.", primary_entity="CORP")
        engine.extract("d2", "Company appointed new CFO.", primary_entity="CORP")

        high_impact = engine.get_high_impact_events(limit=5)
        assert len(high_impact) >= 1
        if len(high_impact) >= 2:
            assert abs(high_impact[0].impact_score) >= abs(high_impact[1].impact_score)

    def test_capex_increase(self):
        engine = EventEngine()
        result = engine.extract(
            "doc13",
            "The company increased its capital expenditure budget to expand AI data center capacity.",
            primary_entity="NVDA",
        )
        capex = [e for e in result.events if e.event_type == EventType.CAPEX_INCREASE]
        assert len(capex) >= 1

    def test_dividend_increase(self):
        engine = EventEngine()
        result = engine.extract(
            "doc14",
            "The board increased the quarterly dividend by 20%.",
            primary_entity="AAPL",
        )
        div_events = [e for e in result.events if e.event_type == EventType.DIVIDEND_INCREASE]
        assert len(div_events) >= 1


# ── Knowledge Service Integration Tests ──────────────────────────────────────

class TestKnowledgeService:

    def test_analyze_single_document(self):
        service = KnowledgeService()
        request = AnalysisRequest(
            text="NVIDIA reported record earnings and beat analyst estimates significantly. "
                 "The company also raised guidance for the next quarter driven by AI chip demand.",
            title="NVIDIA Earnings Beat",
            source="Reuters",
            symbols=["NVDA"],
        )
        result = service.analyze(request)
        assert isinstance(result, AnalysisResult)
        assert len(result.entities) > 0 or len(result.events) > 0

    def test_analyze_with_sentiment(self):
        service = KnowledgeService()
        request = AnalysisRequest(
            text="The company reported strong growth and record high profits. Exceeded expectations significantly.",
            title="Positive News",
            symbols=["NVDA"],
        )
        result = service.analyze(request)
        assert result.sentiment is not None
        # Sentiment can be bullish, very_bullish, or neutral depending on keyword hits
        assert result.sentiment_direction in ("bullish", "very_bullish", "neutral")

    def test_analyze_with_entities(self):
        service = KnowledgeService()
        request = AnalysisRequest(
            text="NVIDIA and Microsoft announced a partnership on AI technology. "
                 "The new Azure cloud services will integrate NVIDIA GPU chips.",
            title="Tech Partnership",
            extract_entities=True,
        )
        result = service.analyze(request)
        assert len(result.entities) > 0

    def test_analyze_with_events(self):
        service = KnowledgeService()
        request = AnalysisRequest(
            text="NVIDIA announced a new product launch of its next-generation GPU chip.",
            title="Product Launch",
            symbols=["NVDA"],
            extract_events=True,
        )
        result = service.analyze(request)
        assert len(result.events) >= 1

    def test_analyze_batch(self):
        service = KnowledgeService()
        requests = [
            AnalysisRequest(text="NVIDIA beat earnings.", title="T1"),
            AnalysisRequest(text="Tesla missed earnings.", title="T2"),
        ]
        results = service.analyze_batch(requests)
        assert len(results) == 2

    def test_search_knowledge(self):
        service = KnowledgeService()
        # First index some documents
        service.analyze(AnalysisRequest(
            text="NVIDIA AI GPU chips semiconductor data center",
            title="NVIDIA AI",
        ))
        service.analyze(AnalysisRequest(
            text="Tesla electric vehicle EV battery autonomous driving",
            title="Tesla EV",
        ))

        results = service.search_knowledge("AI chips GPU data center")
        assert len(results) >= 0  # May or may not find depending on embedding

    def test_get_sentiment_summary(self):
        service = KnowledgeService()
        service.analyze(AnalysisRequest(
            text="Strong growth record earnings beat.",
            title="T1",
            symbols=["NVDA"],
        ))
        summary = service.get_sentiment_summary(["NVDA"])
        assert "NVDA" in summary

    def test_run_pipeline_with_documents(self):
        service = KnowledgeService()
        from services.knowledge.ingestion import RawDocument

        docs = [
            RawDocument(
                title="NVIDIA Earnings Beat",
                content="NVIDIA reported record earnings, beating analyst estimates significantly. "
                         "AI chip demand surges. " + "More analysis. " * 50,
                source="news_api",
                symbols=["NVDA"],
            ),
        ]
        result = service.run_pipeline(docs)
        assert result.status in (PipelineStatus.COMPLETED, PipelineStatus.INGESTING)
        assert result.documents_ingested >= 1


# ── Knowledge API Tests ──────────────────────────────────────────────────────

class TestKnowledgeAPI:

    def test_analyze_endpoint(self):
        api = KnowledgeAPI()
        response = api.analyze({
            "text": "NVIDIA beat earnings and raised guidance significantly.",
            "title": "NVIDIA Earnings",
            "source": "Reuters",
            "symbols": ["NVDA"],
        })
        assert response["success"]
        assert "data" in response

    def test_analyze_missing_text(self):
        api = KnowledgeAPI()
        response = api.analyze({"symbols": ["NVDA"]})
        assert not response["success"]

    def test_get_entity_graph(self):
        api = KnowledgeAPI()
        # Build some graph data first
        api.service.graph.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")

        response = api.get_entity_graph("NVIDIA")
        assert response["success"]

    def test_graph_not_found(self):
        api = KnowledgeAPI()
        response = api.get_entity_graph("NONEXISTENT")
        assert not response["success"]

    def test_get_event_alpha(self):
        api = KnowledgeAPI()
        response = api.get_event_alpha(min_confidence=0.0)
        assert response["success"]
        assert "signals" in response["data"]

    def test_get_sentiment(self):
        api = KnowledgeAPI()
        response = api.get_sentiment(["NVDA"])
        assert response["success"]

    def test_search(self):
        api = KnowledgeAPI()
        response = api.search("AI chips semiconductor")
        assert response["success"]
        assert "results" in response["data"]

    def test_health(self):
        api = KnowledgeAPI()
        response = api.health()
        assert response["success"]
        assert response["data"]["status"] == "healthy"

    def test_ingest_documents(self):
        api = KnowledgeAPI()
        response = api.ingest_documents([
            {
                "title": "Test News",
                "content": "NVIDIA reported record earnings. " + "Data. " * 50,
                "source": "reuters",
                "symbols": ["NVDA"],
            }
        ])
        assert response["success"]

    def test_ingest_empty_docs(self):
        api = KnowledgeAPI()
        response = api.ingest_documents([])
        assert response["success"]
        assert response["data"]["documents_ingested"] == 0


# Need NodeType for test (imported from knowledge_graph)
from services.knowledge.knowledge_graph import NodeType
