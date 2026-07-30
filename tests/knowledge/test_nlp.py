"""
Tests for NLP Processor and Ingestion Pipeline.
"""

import pytest
from services.knowledge.ingestion import (
    IngestionPipeline, IngestionConfig, RawDocument, DocumentType, DataSource, IngestionStatus,
)
from services.knowledge.nlp_processor import (
    NLPProcessor, NLPConfig, NLPResult, NLPTask, NLPTopic,
)
from services.knowledge.news_engine import (
    NewsEngine, NewsConfig, NewsArticle, NewsCategory, NewsSentiment, NewsImpact,
)


# ── Ingestion Tests ──────────────────────────────────────────────────────────

class TestIngestionPipeline:

    def test_create_document(self):
        doc = RawDocument(
            title="Test News",
            content="This is a test news article about AI and semiconductors.",
            source=DataSource.NEWS_API,
            doc_type=DocumentType.NEWS_ARTICLE,
            symbols=["NVDA"],
        )
        assert doc.document_id
        assert doc.content_hash
        assert doc.status == IngestionStatus.PENDING

    def test_ingest_basic(self):
        pipeline = IngestionPipeline()
        docs = [
            RawDocument(
                title="News 1",
                content="Content about NVIDIA and AI chips. " + "More content. " * 50,
                source=DataSource.NEWS_API,
            ),
        ]
        accepted = pipeline.ingest(docs)
        assert len(accepted) == 1
        assert accepted[0].status == IngestionStatus.PROCESSED
        assert pipeline.document_count == 1

    def test_ingest_source_disabled(self):
        pipeline = IngestionPipeline(
            IngestionConfig(enabled_sources={DataSource.REUTERS})
        )
        docs = [
            RawDocument(
                title="News 1",
                content="Content about markets. " + "data " * 50,
                source=DataSource.BLOOMBERG,
            ),
        ]
        accepted = pipeline.ingest(docs)
        assert len(accepted) == 0

    def test_ingest_type_disabled(self):
        pipeline = IngestionPipeline(
            IngestionConfig(enabled_types={DocumentType.NEWS_ARTICLE})
        )
        docs = [
            RawDocument(
                title="Social",
                content="Social media content. " + "test " * 50,
                doc_type=DocumentType.SOCIAL_MEDIA,
                source=DataSource.NEWS_API,
            ),
        ]
        accepted = pipeline.ingest(docs)
        assert len(accepted) == 0

    def test_content_too_short(self):
        pipeline = IngestionPipeline(IngestionConfig(min_content_length=100))
        docs = [
            RawDocument(title="Short", content="Too short", source=DataSource.NEWS_API),
        ]
        accepted = pipeline.ingest(docs)
        assert len(accepted) == 0

    def test_deduplication(self):
        pipeline = IngestionPipeline(IngestionConfig(enable_dedup=True))
        doc = RawDocument(
            title="Dup",
            content="Same content for dedup test. " + "extra " * 50,
            source=DataSource.NEWS_API,
        )
        pipeline.ingest([doc])
        # Second ingestion with same content hash
        doc2 = RawDocument(
            title="Dup",
            content="Same content for dedup test. " + "extra " * 50,
            source=DataSource.NEWS_API,
        )
        accepted = pipeline.ingest([doc2])
        assert len(accepted) == 0  # dedup'd

    def test_filter_transformer(self):
        pipeline = IngestionPipeline()

        # Add filter: only docs with NVDA
        pipeline.add_filter(lambda d: "nvda" in [s.lower() for s in d.symbols])

        # Add transformer: uppercase symbols
        pipeline.add_transformer(lambda d: RawDocument(
            document_id=d.document_id,
            title=d.title,
            content=d.content,
            source=d.source,
            symbols=[s.upper() for s in d.symbols],
        ))

        docs = [
            RawDocument(title="T1", content="Content " * 50, source=DataSource.NEWS_API, symbols=["nvda"]),
            RawDocument(title="T2", content="Content " * 50, source=DataSource.NEWS_API, symbols=["aapl"]),
        ]
        accepted = pipeline.ingest(docs)
        assert len(accepted) == 1
        assert accepted[0].symbols == ["NVDA"]

    def test_query_by_symbols(self):
        pipeline = IngestionPipeline()
        pipeline.ingest([
            RawDocument(title="N1", content="Content " * 50, source=DataSource.NEWS_API, symbols=["NVDA"]),
            RawDocument(title="N2", content="Content2 " * 50, source=DataSource.NEWS_API, symbols=["TSLA"]),
        ])
        results = pipeline.get_documents(symbols=["NVDA"])
        assert len(results) == 1
        assert results[0].title == "N1"


# ── NLP Tests ────────────────────────────────────────────────────────────────

class TestNLPProcessor:

    def test_basic_processing(self):
        nlp = NLPProcessor()
        result = nlp.process("doc1", "NVIDIA announced record earnings and raised guidance for next quarter. AI chip demand surges.")
        assert result.document_id == "doc1"
        assert len(result.topics) > 0
        assert len(result.keywords) > 0

    def test_topic_identification(self):
        nlp = NLPProcessor()
        result = nlp.process("doc1", "The company beat earnings estimates and raised revenue guidance for the year.")
        topic_values = [t.value for t in result.topics]
        assert "earnings" in topic_values

    def test_m_and_a_topic(self):
        nlp = NLPProcessor()
        result = nlp.process(
            "doc2",
            "Company A announced acquisition of Company B in a $10 billion merger deal."
        )
        topic_values = [t.value for t in result.topics]
        assert "merger_acquisition" in topic_values

    def test_regulation_topic(self):
        nlp = NLPProcessor()
        result = nlp.process(
            "doc3",
            "SEC investigation into the company leads to regulatory fine and compliance review."
        )
        topic_values = [t.value for t in result.topics]
        assert "regulation" in topic_values

    def test_positive_direction(self):
        nlp = NLPProcessor()
        result = nlp.process(
            "doc4",
            "The company reported strong growth and beat expectations significantly. Very bullish outlook."
        )
        assert result.direction == "positive"
        assert result.direction_confidence > 0.3

    def test_negative_direction(self):
        nlp = NLPProcessor()
        result = nlp.process(
            "doc5",
            "The company missed earnings, reported a decline in revenue, and issued a weak forecast. Very bearish."
        )
        assert result.direction == "negative"
        assert result.direction_confidence > 0.3

    def test_neutral_direction(self):
        nlp = NLPProcessor()
        result = nlp.process(
            "doc6",
            "The company held its annual general meeting today. Shareholders voted on proposals."
        )
        assert result.direction == "neutral"

    def test_keyword_extraction(self):
        nlp = NLPProcessor(NLPConfig(max_keywords=5))
        result = nlp.process(
            "doc7",
            "NVIDIA artificial intelligence GPU chips semiconductor data center cloud computing AI training inference."
        )
        assert len(result.keywords) <= 5

    def test_summarization(self):
        nlp = NLPProcessor()
        long_text = "First sentence of the article. " + "Middle content. " * 100 + "Final sentence."
        result = nlp.process("doc8", long_text, tasks=[NLPTask.SUMMARIZATION])
        assert len(result.summary) <= 200

    def test_batch_processing(self):
        nlp = NLPProcessor()
        results = nlp.process_batch([
            ("d1", "Strong earnings beat and raised guidance."),
            ("d2", "Regulatory fine and management change."),
        ])
        assert len(results) == 2

    def test_query_by_topic(self):
        nlp = NLPProcessor()
        nlp.process("d1", "Strong earnings beat estimates. Revenue growth impressive.")
        nlp.process("d2", "New AI chip launch breakthrough technology.")
        results = nlp.get_results(topic=NLPTopic.EARNINGS)
        assert len(results) >= 1


# ── News Engine Tests ────────────────────────────────────────────────────────

class TestNewsEngine:

    def test_process_basic(self):
        engine = NewsEngine()
        article = engine.process(
            "doc1",
            "NVIDIA Beats Earnings Estimates",
            "NVIDIA exceeded analyst earnings expectations with record revenue driven by AI chip demand.",
            source="Reuters",
        )
        assert article.title
        assert article.sentiment != NewsSentiment.NEUTRAL
        assert article.sentiment_score > 0.5

    def test_negative_sentiment(self):
        engine = NewsEngine()
        article = engine.process(
            "doc2",
            "Company Misses Earnings, Stock Plunges",
            "The company missed earnings estimates and lowered guidance. Stock price declined sharply.",
            source="Bloomberg",
        )
        assert article.sentiment in (NewsSentiment.NEGATIVE, NewsSentiment.VERY_NEGATIVE)

    def test_breaking_news(self):
        engine = NewsEngine()
        article = engine.process(
            "doc3",
            "BREAKING: Major Acquisition Announcement",
            "Just in: Company A announces acquisition of Company B.",
            source="Reuters",
        )
        assert article.is_breaking

    def test_high_impact(self):
        engine = NewsEngine()
        article = engine.process(
            "doc4",
            "SEC Investigation Leads to Record Fine",
            "The SEC announced a record fine and lawsuit against the company for securities fraud. Bankruptcy risk looms.",
            source="Reuters",
        )
        assert article.impact == NewsImpact.HIGH

    def test_category_earnings(self):
        engine = NewsEngine()
        article = engine.process(
            "doc5",
            "Quarterly Earnings Report Released",
            "The company released its quarterly earnings report showing profit growth.",
        )
        assert NewsCategory.EARNINGS in article.categories

    def test_query_by_sentiment(self):
        engine = NewsEngine()
        engine.process("d1", "Good news", "Strong growth record positive outlook.", source="S1")
        engine.process("d2", "Bad news", "Decline loss weak negative.", source="S2")
        positive = engine.get_articles(sentiment=NewsSentiment.VERY_POSITIVE)
        assert len(positive) >= 1

    def test_breaking_news_query(self):
        engine = NewsEngine()
        engine.process("d1", "BREAKING: Important News", "Urgent alert.", source="S1")
        breaking = engine.get_breaking_news()
        assert len(breaking) >= 1
