"""
Tests for Sentiment Engine and Entity Extraction.
"""

import pytest
from services.knowledge.sentiment import (
    SentimentEngine, SentimentConfig, SentimentResult, SentimentDirection,
    SentimentMomentum, SentimentAcceleration, SentimentTrend,
)
from services.knowledge.entity_extraction import (
    EntityExtractor, ExtractionConfig, ExtractedEntity, EntityType, EntityMention,
)
from services.knowledge.embedding import (
    EmbeddingEngine, EmbeddingConfig, DocumentEmbedding, SimilarityResult, SearchQuery,
)


# ── Sentiment Tests ──────────────────────────────────────────────────────────

class TestSentimentEngine:

    def test_basic_sentiment(self):
        engine = SentimentEngine()
        result = engine.analyze("doc1", "The company reported strong growth and beat expectations significantly.", symbol="NVDA")
        assert result.direction in (SentimentDirection.BULLISH, SentimentDirection.VERY_BULLISH)
        assert result.score > 0.5

    def test_negative_sentiment(self):
        engine = SentimentEngine()
        result = engine.analyze("doc2", "The company reported a sharp decline and missed earnings estimates.", symbol="TSLA")
        assert result.direction in (SentimentDirection.BEARISH, SentimentDirection.VERY_BEARISH)
        assert result.score < 0.5

    def test_neutral_sentiment(self):
        engine = SentimentEngine()
        result = engine.analyze("doc3", "The company is holding a meeting today about general business updates.", symbol="AAPL")
        assert result.direction == SentimentDirection.NEUTRAL

    def test_dimensions(self):
        engine = SentimentEngine()
        result = engine.analyze("doc4", "The company beat earnings estimates with strong revenue growth.", symbol="NVDA")
        assert "earnings" in result.dimensions

    def test_confidence(self):
        engine = SentimentEngine()
        result = engine.analyze(
            "doc5",
            "surge record high breakthrough strong beat exceed growth rally",
            symbol="NVDA",
        )
        assert result.confidence > 0.1

    def test_batch_analysis(self):
        engine = SentimentEngine()
        results = engine.analyze_batch([
            ("d1", "Strong growth and record earnings beat.", "NVDA"),
            ("d2", "Decline and loss, weak performance.", "TSLA"),
        ])
        assert len(results) == 2
        assert results[0].score > results[1].score

    def test_symbol_sentiment(self):
        engine = SentimentEngine()
        engine.analyze("d1", "Strong growth record earnings beat surge breakthrough.", symbol="NVDA")
        engine.analyze("d2", "New AI chip launch breakthrough record high.", symbol="NVDA")
        agg = engine.get_symbol_sentiment("NVDA")
        assert agg.direction in (SentimentDirection.BULLISH, SentimentDirection.VERY_BULLISH)

    def test_no_symbol_results(self):
        engine = SentimentEngine()
        agg = engine.get_symbol_sentiment("NONEXISTENT")
        assert agg.direction == SentimentDirection.NEUTRAL
        assert agg.score == 0.5

    def test_momentum_basic(self):
        engine = SentimentEngine()
        for i in range(10):
            engine.analyze(f"d{i}", "Strong growth and record earnings.", symbol="NVDA")
        momentum = engine.compute_momentum("NVDA")
        assert momentum.symbol == "NVDA"
        assert momentum.num_samples >= engine.config.min_samples_for_momentum

    def test_momentum_insufficient_data(self):
        engine = SentimentEngine()
        engine.analyze("d1", "Test content.", symbol="SPARSE")
        momentum = engine.compute_momentum("SPARSE")
        assert momentum.num_samples == 1

    def test_acceleration(self):
        engine = SentimentEngine()
        for i in range(10):
            engine.analyze(f"d{i}", "Strong growth record earnings.", symbol="NVDA")
        engine.compute_momentum("NVDA")
        accel = engine.compute_acceleration("NVDA")
        assert accel.symbol == "NVDA"

    def test_query_by_direction(self):
        engine = SentimentEngine()
        engine.analyze("d1", "Growth improve advance opportunity.", symbol="NVDA")
        engine.analyze("d2", "Decline loss weak.", symbol="TSLA")
        results = engine.get_results(direction=SentimentDirection.BULLISH)
        assert len(results) >= 1


# ── Entity Extraction Tests ──────────────────────────────────────────────────

class TestEntityExtractor:

    def test_extract_company(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc1",
            "NVIDIA announced new AI chips and partnership with Microsoft and Google.",
        )
        company_names = [e.canonical_name.lower() for e in entities if e.entity_type == EntityType.COMPANY]
        assert "nvidia" in company_names
        assert "microsoft" in company_names or "google" in company_names

    def test_extract_ticker(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc2",
            "The stock $NVDA surged while $AMD also gained.",
        )
        tickers = [e.ticker for e in entities if e.entity_type == EntityType.TICKER]
        assert "NVDA" in tickers

    def test_extract_product(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc3",
            "The new iPhone and Azure cloud services showed strong growth.",
        )
        products = [e.name.lower() for e in entities if e.entity_type == EntityType.PRODUCT]
        assert "iphone" in products or "azure" in products

    def test_extract_industry(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc4",
            "The semiconductor industry and cloud computing sectors are growing rapidly.",
        )
        types = [e.entity_type for e in entities]
        assert EntityType.INDUSTRY in types

    def test_extract_person(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc5",
            "Jensen Huang announced the new product line during the keynote.",
        )
        persons = [e.name.lower() for e in entities if e.entity_type == EntityType.PERSON]
        assert len(persons) >= 1
        assert "jensen huang" in persons

    def test_mention_count(self):
        extractor = EntityExtractor()
        entities = extractor.extract(
            "doc6",
            "NVIDIA NVIDIA NVIDIA chips are led by NVIDIA CEO. NVIDIA is the leader."
        )
        nvidia = None
        for e in entities:
            if e.name.lower() == "nvidia":
                nvidia = e
                break
        assert nvidia is not None
        assert nvidia.mention_count >= 3

    def test_find_by_ticker(self):
        extractor = EntityExtractor()
        extractor.extract("doc1", "NVIDIA is a leading AI chip company.")
        entity = extractor.get_by_ticker("NVDA")
        assert entity is not None
        assert entity.name.lower() == "nvidia"

    def test_find_by_name(self):
        extractor = EntityExtractor()
        extractor.extract("doc1", "Apple released a new iPhone.")
        entity = extractor.find_entity("apple")
        assert entity is not None

    def test_get_by_type(self):
        extractor = EntityExtractor()
        extractor.extract("doc1", "NVIDIA and AMD are chip makers. The iPhone is popular.")
        companies = extractor.get_by_type(EntityType.COMPANY)
        assert len(companies) >= 1


# ── Embedding Tests ──────────────────────────────────────────────────────────

class TestEmbeddingEngine:

    def test_embed_single(self):
        engine = EmbeddingEngine()
        emb = engine.embed(
            "doc1",
            keywords=["nvidia", "ai", "chip", "semiconductor", "gpu"],
            keyword_scores={"nvidia": 1.0, "ai": 0.8, "chip": 0.7, "semiconductor": 0.6, "gpu": 0.5},
            title="NVIDIA AI Chips",
        )
        assert emb.document_id == "doc1"
        assert emb.dimension > 0

    def test_similarity_search(self):
        engine = EmbeddingEngine()
        engine.embed(
            "doc1",
            keywords=["nvidia", "ai", "chip", "gpu", "semiconductor"],
            keyword_scores={"nvidia": 1.0, "ai": 0.9, "chip": 0.8, "gpu": 0.7, "semiconductor": 0.6},
            title="NVIDIA AI",
        )
        engine.embed(
            "doc2",
            keywords=["tesla", "electric", "vehicle", "battery", "ev"],
            keyword_scores={"tesla": 1.0, "electric": 0.9, "vehicle": 0.5, "battery": 0.4, "ev": 0.6},
            title="Tesla EV",
        )

        results = engine.search_by_text("nvidia gpu ai chip")
        assert len(results) > 0
        assert "doc1" in [r.embedding.document_id for r in results]

    def test_find_similar(self):
        engine = EmbeddingEngine()
        engine.embed(
            "doc1",
            keywords=["nvidia", "ai", "chip", "gpu"],
            keyword_scores={"nvidia": 1.0, "ai": 0.8, "chip": 0.7, "gpu": 0.6},
        )
        engine.embed(
            "doc2",
            keywords=["nvidia", "ai", "semiconductor", "data center"],
            keyword_scores={"nvidia": 0.9, "ai": 0.8, "semiconductor": 0.6, "data center": 0.5},
        )
        engine.embed(
            "doc3",
            keywords=["tesla", "ev", "battery", "electric"],
            keyword_scores={"tesla": 1.0, "ev": 0.8, "battery": 0.6, "electric": 0.5},
        )

        similar = engine.find_similar("doc1", top_k=3)
        assert len(similar) > 0
        # doc2 should be more similar than doc3
        sims = {r.embedding.document_id: r.similarity for r in similar}
        if "doc2" in sims and "doc3" in sims:
            assert sims["doc2"] > sims["doc3"]

    def test_search_by_symbol(self):
        engine = EmbeddingEngine()
        engine.embed("doc1", keywords=["nvidia", "ai"], symbols=["NVDA"])
        engine.embed("doc2", keywords=["tesla", "ev"], symbols=["TSLA"])

        results = engine.search(
            SearchQuery(text="ai chips", symbols=["NVDA"], top_k=5)
        )
        nvda_results = [r for r in results if "NVDA" in r.embedding.symbols]
        assert len(nvda_results) >= 1

    def test_clustering(self):
        engine = EmbeddingEngine()
        engine.embed("doc1", keywords=["ai", "ml", "deep learning", "neural network"])
        engine.embed("doc2", keywords=["ai", "gpu", "training", "inference"])
        engine.embed("doc3", keywords=["oil", "gas", "energy", "crude"])
        engine.embed("doc4", keywords=["solar", "wind", "renewable", "energy"])

        clusters = engine.cluster_by_similarity(threshold=0.3)
        assert len(clusters) >= 1
