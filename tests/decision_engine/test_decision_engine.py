from services.decision_engine import (
    ApprovalWorkflow,
    AuditRecord,
    Candidate,
    Decision,
    DecisionAudit,
    DecisionScoringEngine,
    DecisionService,
    RiskAdjustedSelector,
    SignalFusionEngine,
    StrategyRankingEngine,
    StrategyScore,
)


def test_decision_engine():
    """Basic decision engine test from the spec."""
    fusion = SignalFusionEngine()
    service = DecisionService(fusion)

    result = service.decide([0.8, 0.9])
    assert abs(result - 0.85) < 1e-9


def test_decision_model():
    """Test Decision dataclass lifecycle."""
    d = Decision(symbol="NVDA", action="BUY", score=0.85)
    assert d.symbol == "NVDA"
    assert d.action == "BUY"
    assert d.score == 0.85
    assert d.status == "PENDING"


def test_decision_approval_lifecycle():
    """Test full approval lifecycle of a Decision."""
    d = Decision(symbol="AAPL", action="BUY", score=0.75)

    assert d.status == "PENDING"
    d.approve()
    assert d.status == "APPROVED"
    assert d.approved_at is not None

    d.execute()
    assert d.status == "EXECUTED"
    assert d.executed_at is not None

    d2 = Decision(symbol="TSLA", action="SELL", score=0.3)
    d2.reject("Risk too high")
    assert d2.status == "REJECTED"
    assert d2.reason == "Risk too high"


def test_decision_is_actionable():
    """Test actionable check."""
    d1 = Decision(symbol="MSFT", action="BUY", score=0.8, status="APPROVED")
    assert d1.is_actionable()

    d2 = Decision(symbol="GOOG", action="BUY", score=0.0, status="APPROVED")
    assert not d2.is_actionable()

    d3 = Decision(symbol="META", action="BUY", score=0.9, status="PENDING")
    assert not d3.is_actionable()


def test_signal_fusion_simple():
    """Test simple equal-weight fusion."""
    fusion = SignalFusionEngine()
    result = fusion.combine([0.1, 0.3, 0.5])
    assert result == 0.3

    result = fusion.combine([1.0])
    assert result == 1.0

    result = fusion.combine([])
    assert result == 0.0


def test_signal_fusion_weighted():
    """Test weighted signal fusion."""
    fusion = SignalFusionEngine(
        default_weights={"momentum": 0.5, "ml": 0.3, "factor": 0.2}
    )

    signals = {"momentum": 0.8, "ml": 0.6, "factor": 0.4}
    result = fusion.combine_weighted(signals)
    assert 0.5 < result < 0.7


def test_signal_fusion_confidence():
    """Test confidence-weighted fusion."""
    fusion = SignalFusionEngine()

    signals = {"model_a": 0.9, "model_b": 0.5}
    confidences = {"model_a": 0.95, "model_b": 0.4}

    result = fusion.fuse_with_confidence(signals, confidences)
    assert "score" in result
    assert "confidence" in result
    assert result["confidence"] <= 1.0
    assert result["confidence"] > 0.0


def test_scoring_basic():
    """Test basic scoring: alpha - risk."""
    engine = DecisionScoringEngine()
    result = engine.score(0.8, 0.2)
    assert result == 0.6

    result = engine.score(0.3, 0.5)
    assert result == -0.2


def test_scoring_full():
    """Test full scoring with model confidence."""
    engine = DecisionScoringEngine()
    result = engine.score_full(
        alpha=0.7, model_confidence=0.8, risk_penalty=0.3
    )
    assert result["alpha"] == 0.7
    assert result["model_confidence"] == 0.8
    assert result["risk_penalty"] == 0.3
    assert result["final_score"] > 0


def test_scoring_determine_action():
    """Test BUY/SELL/HOLD determination."""
    engine = DecisionScoringEngine()

    assert engine.determine_action(0.8, 0.1) == "BUY"
    assert engine.determine_action(0.1, 0.8) == "SELL"
    assert engine.determine_action(0.5, 0.4) == "HOLD"


def test_scoring_multi_factor():
    """Test multi-factor scoring."""
    engine = DecisionScoringEngine()

    scores = {"momentum": 0.8, "value": 0.4, "quality": 0.6}
    result = engine.score_multi_factor(scores)
    assert result == 0.6

    weights = {"momentum": 2.0, "value": 1.0, "quality": 1.0}
    result = engine.score_multi_factor(scores, weights)
    assert result > 0.6


def test_strategy_ranking():
    """Test strategy ranking by score."""
    engine = StrategyRankingEngine()

    s1 = StrategyScore(name="Momentum", sharpe=1.5, score=0.5)
    s2 = StrategyScore(name="MeanRev", sharpe=2.1, score=0.9)
    s3 = StrategyScore(name="ML", sharpe=1.8, score=0.7)

    ranked = engine.rank([s1, s2, s3])
    assert len(ranked) == 3
    assert ranked[0].name == "MeanRev"  # highest score
    assert ranked[0].rank == 1
    assert ranked[2].name == "Momentum"  # lowest score
    assert ranked[2].rank == 3


def test_strategy_ranking_by_metric():
    """Test ranking by specific metrics."""
    engine = StrategyRankingEngine()

    s1 = StrategyScore(name="A", sharpe=1.0, returns=0.15, max_drawdown=-0.05)
    s2 = StrategyScore(name="B", sharpe=2.0, returns=0.10, max_drawdown=-0.20)
    s3 = StrategyScore(name="C", sharpe=1.5, returns=0.20, max_drawdown=-0.10)

    ranked = engine.rank_by_metric([s1, s2, s3], "sharpe")
    assert ranked[0].name == "B"  # highest sharpe
    assert ranked[2].name == "A"

    ranked = engine.rank_by_metric([s1, s2, s3], "returns")
    assert ranked[0].name == "C"  # highest returns


def test_strategy_ranking_top_n():
    """Test top N selection."""
    engine = StrategyRankingEngine()

    strategies = []
    for i in range(5):
        s = StrategyScore(
            name=f"Strategy_{i}", sharpe=0.5 + i * 0.3, returns=0.1 + i * 0.02
        )
        strategies.append(s)

    top = engine.top_n(strategies, n=2)
    assert len(top) == 2
    assert top[0].rank == 1
    assert top[1].rank == 2


def test_risk_adjusted_selector():
    """Test risk-adjusted candidate selection."""
    selector = RiskAdjustedSelector(risk_aversion=2.0)

    c1 = Candidate(
        name="Tech", symbol="XLK", expected_return=0.3, volatility=0.15
    )
    c2 = Candidate(
        name="Bonds", symbol="TLT", expected_return=0.2, volatility=0.05
    )

    selected = selector.select([c1, c2])
    # Score: c1 = 0.3 - 2*0.15 = 0.0, c2 = 0.2 - 2*0.05 = 0.1
    assert selected.symbol == "TLT"


def test_risk_adjusted_filter():
    """Test candidate filtering by risk constraints."""
    selector = RiskAdjustedSelector(
        min_sharpe=0.5, max_volatility=0.2, max_drawdown_limit=0.15
    )

    c1 = Candidate(
        name="Safe", sharpe=1.0, volatility=0.10, max_drawdown=-0.05
    )
    c2 = Candidate(
        name="Risky", sharpe=1.5, volatility=0.30, max_drawdown=-0.40
    )

    result = selector.select_with_score([c1, c2])
    assert result is not None
    assert result.name == "Safe"
    assert result.metadata["total_candidates"] == 2
    assert result.metadata["passed_filter"] == 1


def test_risk_adjusted_top_n():
    """Test top N risk-adjusted selection."""
    selector = RiskAdjustedSelector()

    candidates = [
        Candidate(name="A", symbol="A", expected_return=0.25, volatility=0.10),
        Candidate(name="B", symbol="B", expected_return=0.15, volatility=0.05),
        Candidate(name="C", symbol="C", expected_return=0.35, volatility=0.20),
    ]

    top = selector.select_top_n(candidates, n=2)
    assert len(top) == 2
    assert top[0].score >= top[1].score


def test_approval_workflow():
    """Test approval workflow state machine."""
    wf = ApprovalWorkflow()

    d1 = Decision(symbol="NVDA", action="BUY", score=0.85)
    d2 = Decision(symbol="AMD", action="SELL", score=0.4)

    # Submit
    wf.submit(d1)
    wf.submit(d2)
    assert len(wf.get_pending()) == 2

    # Approve one
    wf.approve(d1)
    assert d1.status == "APPROVED"
    assert len(wf.get_pending()) == 1

    # Reject one
    wf.reject(d2, "Insufficient alpha")
    assert d2.status == "REJECTED"
    assert d2.reason == "Insufficient alpha"
    assert len(wf.get_pending()) == 0


def test_approval_auto():
    """Test auto-approval based on score threshold."""
    wf = ApprovalWorkflow()

    d_high = Decision(symbol="AAPL", action="BUY", score=0.9)
    d_low = Decision(symbol="IBM", action="HOLD", score=0.4)

    wf.auto_approve(d_high, threshold=0.7)
    assert d_high.status == "APPROVED"

    wf.auto_approve(d_low, threshold=0.7)
    assert d_low.status == "PENDING"


def test_approval_execute():
    """Test execution of approved decisions."""
    wf = ApprovalWorkflow()

    d = Decision(symbol="MSFT", action="BUY", score=0.8)
    wf.submit(d)
    wf.approve(d)
    wf.execute(d)
    assert d.status == "EXECUTED"


def test_approval_summary():
    """Test approval workflow summary."""
    wf = ApprovalWorkflow()

    d1 = Decision(symbol="A", action="BUY", score=0.8)
    d2 = Decision(symbol="B", action="BUY", score=0.6)
    d3 = Decision(symbol="C", action="SELL", score=0.3)

    wf.submit(d1)
    wf.approve(d1)

    wf.submit(d2)
    wf.reject(d2, "weak")

    wf.submit(d3)

    summary = wf.summary()
    assert summary["total_decisions"] == 2
    assert summary["approved"] == 1
    assert summary["rejected"] == 1
    assert summary["pending"] == 1


def test_decision_audit():
    """Test audit trail recording."""
    audit = DecisionAudit()

    d1 = Decision(
        symbol="NVDA", action="BUY", score=0.85, reason="Momentum strong"
    )
    d2 = Decision(
        symbol="INTC", action="SELL", score=0.2, reason="Weak outlook"
    )

    audit.record(d1)
    audit.record(d2)

    assert len(audit.records) == 2

    nvda_records = audit.get_by_symbol("NVDA")
    assert len(nvda_records) == 1
    assert nvda_records[0].reason == "Momentum strong"


def test_audit_filtering():
    """Test audit querying by status."""
    audit = DecisionAudit()

    d1 = Decision(symbol="A", action="BUY", score=0.8, status="APPROVED")
    d2 = Decision(symbol="B", action="SELL", score=0.3, status="REJECTED")
    d3 = Decision(symbol="C", action="BUY", score=0.7, status="EXECUTED")

    audit.record(d1)
    audit.record(d2)
    audit.record(d3)

    approved = audit.get_by_status("APPROVED")
    assert len(approved) == 1
    assert approved[0].decision.symbol == "A"


def test_audit_summary():
    """Test audit summary statistics."""
    audit = DecisionAudit()

    audit.record(Decision(symbol="A", action="BUY", score=0.8))
    audit.record(Decision(symbol="B", action="SELL", score=0.4))
    audit.record(Decision(symbol="C", action="BUY", score=0.6))

    summary = audit.summary()
    assert summary["total_records"] == 3
    assert summary["actions"]["BUY"] == 2
    assert summary["actions"]["SELL"] == 1


def test_audit_detailed_record():
    """Test detailed audit recording with market regime."""
    audit = DecisionAudit()

    d = Decision(symbol="AAPL", action="BUY", score=0.9)

    audit.record_detailed(
        d,
        signal_details={"momentum": 0.85, "ml_pred": 0.78},
        risk_metrics={"volatility": 0.12, "var_95": 0.02},
        market_regime="bull",
    )

    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.market_regime == "bull"
    assert record.signal_details["momentum"] == 0.85
    assert record.risk_metrics["volatility"] == 0.12


def test_audit_recent():
    """Test getting recent audit records."""
    audit = DecisionAudit()

    for i in range(15):
        audit.record(Decision(symbol=f"S{i}", action="BUY", score=0.5 + i * 0.03))

    recent = audit.get_recent(5)
    assert len(recent) == 5
    # Records are stored in insertion order; get_recent returns last 5 reversed
    recent_symbols = {r.decision.symbol for r in recent}
    expected = {"S10", "S11", "S12", "S13", "S14"}
    assert recent_symbols == expected


def test_decision_service_pipeline():
    """Test full decision service pipeline."""
    fusion = SignalFusionEngine()
    scoring = DecisionScoringEngine()
    approval = ApprovalWorkflow()
    audit = DecisionAudit()

    service = DecisionService(
        fusion=fusion,
        scoring=scoring,
        approval=approval,
        audit=audit,
    )

    decision = service.decide_full(
        symbol="NVDA",
        signals=[0.85, 0.78, 0.82],
        alpha=0.7,
        risk=0.1,
    )

    assert decision.symbol == "NVDA"
    assert decision.action == "BUY"
    assert decision.score > 0
    assert decision.status == "PENDING"

    # Approve and execute
    service.approve_decision(decision, approved=True)
    assert decision.status == "APPROVED"

    service.execute_decision(decision)
    assert decision.status == "EXECUTED"


def test_decision_service_weighted():
    """Test weighted decision pipeline."""
    service = DecisionService(fusion=SignalFusionEngine())

    signals = {"momentum": 0.85, "ml": 0.72, "factor": 0.68}
    weights = {"momentum": 0.5, "ml": 0.3, "factor": 0.2}

    decision = service.decide_weighted("AAPL", signals, weights)
    assert decision.symbol == "AAPL"
    assert decision.status == "PENDING"
    assert decision.score > 0


def test_decision_service_rank():
    """Test strategy ranking through service."""
    service = DecisionService(fusion=SignalFusionEngine())

    strategies = [
        StrategyScore(name="A", sharpe=1.0, returns=0.1),
        StrategyScore(name="B", sharpe=2.5, returns=0.2),
        StrategyScore(name="C", sharpe=1.8, returns=0.15),
    ]

    ranked = service.rank_strategies(strategies)
    assert len(ranked) == 3
    assert ranked[0].name == "B"


def test_decision_service_select():
    """Test candidate selection through service."""
    service = DecisionService(
        fusion=SignalFusionEngine(),
        selector=RiskAdjustedSelector(risk_aversion=1.0),
    )

    candidates = [
        Candidate(name="Tech", symbol="XLK", expected_return=0.25, volatility=0.15, sharpe=1.5),
        Candidate(name="Bonds", symbol="TLT", expected_return=0.10, volatility=0.05, sharpe=1.2),
    ]

    selected = service.select_best(candidates)
    assert selected is not None
    # Tech: 0.25 - 1*0.15 = 0.10, Bonds: 0.10 - 1*0.05 = 0.05
    assert selected.symbol == "XLK"


def test_pipeline_summary():
    """Test pipeline summary."""
    service = DecisionService(fusion=SignalFusionEngine())

    service.decide_full(symbol="A", signals=[0.8, 0.7], alpha=0.6, risk=0.1)
    service.decide_full(symbol="B", signals=[0.3, 0.4], alpha=0.2, risk=0.6)

    summary = service.pipeline_summary()
    assert "approval" in summary
    assert "audit" in summary
    assert summary["audit"]["total_records"] == 2


def test_risk_adjusted_select_by_sharpe():
    """Test selection by Sharpe ratio."""
    selector = RiskAdjustedSelector()

    c1 = Candidate(name="A", sharpe=0.5, expected_return=0.15, volatility=0.10)
    c2 = Candidate(name="B", sharpe=2.0, expected_return=0.10, volatility=0.05)

    selected = selector.select_by_sharpe([c1, c2])
    assert selected.name == "B"


def test_selector_empty():
    """Test selector raises on empty candidates."""
    selector = RiskAdjustedSelector()
    try:
        selector.select([])
        assert False, "Should raise ValueError"
    except ValueError:
        pass
