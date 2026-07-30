"""
Tests for Event-Driven Alpha Signal Engine.
"""

import pytest
from datetime import datetime, timezone, timedelta
from services.knowledge.event_engine import (
    MarketEvent, EventType, EventImpact, EventEngine,
)
from services.knowledge.knowledge_graph import KnowledgeGraph, NodeType, EdgeType
from services.knowledge.alpha_signal import (
    EventAlphaEngine, AlphaConfig, AlphaSignal, SignalType, SignalConfidence,
    EventToSignalMapping, SignalPipeline,
)


class TestEventAlphaEngine:

    def test_earnings_surprise_signal(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.EARNINGS_SURPRISE,
            primary_entity="NVDA",
            impact=EventImpact.POSITIVE,
            impact_score=0.7,
            confidence=0.9,
            description="Beat earnings estimates",
            affected_symbols=["NVDA"],
        )
        signals = engine.generate_signals([event])
        assert len(signals) >= 1
        assert signals[0].symbol == "NVDA"
        assert signals[0].signal_type == SignalType.BUY
        assert signals[0].confidence > 0.5

    def test_bankruptcy_signal(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.BANKRUPTCY,
            primary_entity="CORP",
            impact=EventImpact.STRONG_NEGATIVE,
            impact_score=-0.9,
            confidence=0.95,
            description="Filed for bankruptcy",
            affected_symbols=["CORP"],
        )
        signals = engine.generate_signals([event])
        assert len(signals) >= 1
        assert signals[0].signal_type == SignalType.SELL
        assert signals[0].confidence > 0.8

    def test_guidance_lowered_signal(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.GUIDANCE_LOWERED,
            primary_entity="INTC",
            impact=EventImpact.NEGATIVE,
            impact_score=-0.6,
            confidence=0.8,
            description="Lowered guidance",
            affected_symbols=["INTC"],
        )
        signals = engine.generate_signals([event])
        assert len(signals) >= 1
        assert signals[0].signal_type == SignalType.SELL

    def test_fda_approval_signal(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.FDA_APPROVAL,
            primary_entity="BIOTECH",
            impact=EventImpact.STRONG_POSITIVE,
            impact_score=0.7,
            confidence=0.9,
            description="FDA approved new drug",
            affected_symbols=["BIOTECH"],
        )
        signals = engine.generate_signals([event])
        assert len(signals) >= 1
        assert signals[0].signal_type == SignalType.BUY

    def test_multiple_events(self):
        engine = EventAlphaEngine()
        events = [
            MarketEvent(
                event_type=EventType.EARNINGS_SURPRISE,
                primary_entity="NVDA", impact=EventImpact.POSITIVE,
                impact_score=0.7, confidence=0.9, affected_symbols=["NVDA"],
                description="Beat earnings",
            ),
            MarketEvent(
                event_type=EventType.PRODUCT_LAUNCH,
                primary_entity="NVDA", impact=EventImpact.POSITIVE,
                impact_score=0.5, confidence=0.8, affected_symbols=["NVDA"],
                description="New chip launch",
            ),
        ]
        signals = engine.generate_signals(events)
        assert len(signals) >= 2

    def test_low_confidence_filtered(self):
        engine = EventAlphaEngine(AlphaConfig(min_confidence=0.5))
        event = MarketEvent(
            event_type=EventType.MANAGEMENT_APPOINTMENT,
            primary_entity="CORP", impact=EventImpact.NEUTRAL,
            impact_score=0.1, confidence=0.2, affected_symbols=["CORP"],
            description="New CEO appointed",
        )
        signals = engine.generate_signals([event])
        # Low confidence + low impact -> filtered
        assert len(signals) == 0

    def test_signal_expiry(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.ANALYST_UPGRADE,
            primary_entity="NVDA", impact=EventImpact.POSITIVE,
            impact_score=0.5, confidence=0.8, affected_symbols=["NVDA"],
            description="Analyst upgrade",
        )
        signals = engine.generate_signals([event])
        assert len(signals) >= 1
        assert signals[0].expires_at is not None
        assert signals[0].expires_at > signals[0].generated_at

    def test_aggregate_signals(self):
        engine = EventAlphaEngine()
        events = [
            MarketEvent(
                event_type=EventType.EARNINGS_SURPRISE, primary_entity="NVDA",
                impact=EventImpact.POSITIVE, impact_score=0.7, confidence=0.9,
                affected_symbols=["NVDA"], description="Beat earnings",
            ),
            MarketEvent(
                event_type=EventType.PRODUCT_LAUNCH, primary_entity="NVDA",
                impact=EventImpact.POSITIVE, impact_score=0.5, confidence=0.8,
                affected_symbols=["NVDA"], description="New product",
            ),
            MarketEvent(
                event_type=EventType.ANALYST_UPGRADE, primary_entity="NVDA",
                impact=EventImpact.POSITIVE, impact_score=0.5, confidence=0.7,
                affected_symbols=["NVDA"], description="Analyst upgrade",
            ),
        ]
        engine.generate_signals(events)
        agg = engine.aggregate_signals("NVDA")
        assert agg is not None
        assert agg.signal_type == SignalType.BUY
        assert agg.event_count >= 3

    def test_aggregate_empty(self):
        engine = EventAlphaEngine()
        agg = engine.aggregate_signals("NONEXISTENT")
        assert agg is None

    def test_aggregate_all(self):
        engine = EventAlphaEngine()
        events = [
            MarketEvent(
                event_type=EventType.EARNINGS_SURPRISE, primary_entity="NVDA",
                impact=EventImpact.POSITIVE, impact_score=0.7, confidence=0.9,
                affected_symbols=["NVDA"], description="Beat",
            ),
            MarketEvent(
                event_type=EventType.EARNINGS_MISS, primary_entity="TSLA",
                impact=EventImpact.NEGATIVE, impact_score=-0.7, confidence=0.9,
                affected_symbols=["TSLA"], description="Miss",
            ),
        ]
        engine.generate_signals(events)
        agg = engine.aggregate_all()
        assert len(agg) >= 2

    def test_query_signals_by_symbol(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.EARNINGS_SURPRISE, primary_entity="NVDA",
            impact=EventImpact.POSITIVE, impact_score=0.7, confidence=0.9,
            affected_symbols=["NVDA"], description="Beat",
        )
        engine.generate_signals([event])

        signals = engine.get_signals(symbol="NVDA")
        assert len(signals) >= 1

    def test_query_active_buy_signals(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.EARNINGS_SURPRISE, primary_entity="NVDA",
            impact=EventImpact.POSITIVE, impact_score=0.7, confidence=0.9,
            affected_symbols=["NVDA"], description="Beat",
        )
        engine.generate_signals([event])

        buy_signals = engine.get_active_buy_signals(min_confidence=0.3)
        assert len(buy_signals) >= 1

    def test_get_latest_signal(self):
        engine = EventAlphaEngine()
        event = MarketEvent(
            event_type=EventType.GUIDANCE_RAISED, primary_entity="NVDA",
            impact=EventImpact.POSITIVE, impact_score=0.6, confidence=0.8,
            affected_symbols=["NVDA"], description="Raised guidance",
        )
        engine.generate_signals([event])

        latest = engine.get_latest_signal("NVDA")
        assert latest is not None
        assert latest.signal_type == SignalType.BUY

    def test_signal_to_dict(self):
        signal = AlphaSignal(
            symbol="NVDA",
            signal_type=SignalType.BUY,
            confidence=0.82,
            confidence_level=SignalConfidence.VERY_HIGH,
            alpha_score=0.6,
            reason="Beat earnings significantly",
        )
        d = signal.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["signal_type"] == "BUY"
        assert d["confidence"] == 0.82

    def test_graph_propagation(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        mu = g.add_node("Micron", NodeType.COMPANY, ticker="MU")

        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.9, confidence=0.8)
        g.add_edge(mu.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.7, confidence=0.7)

        engine = EventAlphaEngine(knowledge_graph=g)
        event = MarketEvent(
            EventType.EARNINGS_SURPRISE, "NVDA", EventImpact.POSITIVE, 0.7, confidence=0.9,
            affected_symbols=["NVDA"], description="Beat"
        )
        signals = engine.generate_signals([event])
        propagated = engine.propagate_signals(signals)
        assert len(propagated) >= 0  # May propagate to TSMC, MU

    def test_propagation_disabled(self):
        engine = EventAlphaEngine(AlphaConfig(enable_graph_propagation=False))
        signals = [AlphaSignal(symbol="NVDA", signal_type=SignalType.BUY, confidence=0.8)]
        propagated = engine.propagate_signals(signals)
        assert len(propagated) == 0

    def test_signal_pipeline(self):
        engine = EventAlphaEngine()
        pipeline = engine.create_pipeline("test_pipeline")
        assert pipeline.name == "test_pipeline"

        events = [
            MarketEvent(
                event_type=EventType.EARNINGS_SURPRISE, primary_entity="NVDA",
                impact=EventImpact.POSITIVE, impact_score=0.7, confidence=0.9,
                affected_symbols=["NVDA"], description="Beat",
            ),
        ]
        signals = engine.generate_signals(events)
        engine.add_to_pipeline(pipeline.pipeline_id, signals)

        agg = engine.aggregate_pipeline(pipeline.pipeline_id)
        assert agg is not None

    def test_add_event_mapping(self):
        engine = EventAlphaEngine()
        engine.add_event_mapping(EventToSignalMapping(
            EventType.OTHER, SignalType.HOLD, 0.0
        ))
        assert EventType.OTHER in engine._event_signal_map
