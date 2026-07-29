from services.investment_decision import *


def test_thesis_generator():
    engine = InvestmentThesisGenerator()
    result = engine.generate("AI Chip")
    assert result["thesis"] == "AI Chip"


def test_thesis_generator_with_thesis():
    engine = InvestmentThesisGenerator()
    thesis = InvestmentThesis(
        thesis_id="T001",
        symbol="NVDA",
        thesis_type=ThesisType.GROWTH,
        title="AI Semiconductor Growth",
        why_buy="Dominant position in AI GPU market",
        why_now="AI capex cycle accelerating",
        catalyst="New product launch in Q4",
        risks=["Competition from AMD", "Cyclical semiconductor risk"],
        exit_conditions=["AI capex growth slows", "Market share declines >5%"],
        expected_return=0.25,
        time_horizon="12M",
        confidence=ThesisConfidence.HIGH,
    )
    result = engine.generate(thesis)
    assert result["thesis"]["thesis_id"] == "T001"
    assert result["thesis"]["type"] == "GROWTH"
    assert result["thesis"]["symbol"] == "NVDA"
    assert result["thesis"]["confidence"] == "HIGH"
    assert len(result["thesis"]["risks"]) == 2


def test_thesis_validation():
    engine = InvestmentThesisGenerator()
    # Valid thesis
    valid_thesis = InvestmentThesis(
        thesis_id="T001", symbol="NVDA", thesis_type=ThesisType.GROWTH,
        title="Test", why_buy="Strong growth", why_now="Timing right",
        catalyst="Product launch", risks=["Competition"],
        exit_conditions=["Growth slows"],
    )
    result = engine.validate_thesis(valid_thesis)
    assert result["valid"] is True

    # Invalid thesis
    invalid_thesis = InvestmentThesis(
        thesis_id="T002", symbol="TEST", thesis_type=ThesisType.GROWTH,
        title="Test", why_buy="", why_now="", catalyst="",
        risks=[], exit_conditions=[],
    )
    result = engine.validate_thesis(invalid_thesis)
    assert result["valid"] is False
    assert len(result["issues"]) == 5


def test_opportunity_evaluation():
    engine = OpportunityEvaluationEngine()
    result = engine.evaluate("AAPL")
    assert result["evaluation"] == "AAPL"


def test_opportunity_evaluation_with_profile():
    engine = OpportunityEvaluationEngine()
    profile = OpportunityProfile(
        symbol="NVDA",
        sector="Technology",
        market_cap=1000000000000.0,
        growth_rate=0.25,
        pe_ratio=35.0,
        competitive_moat="strong",
        risk_score=40.0,
        market_opportunity="AI infrastructure",
    )
    result = engine.evaluate(profile)
    assert result["evaluation"]["symbol"] == "NVDA"
    assert result["evaluation"]["rating"] in (
        "EXCELLENT", "GOOD", "FAIR", "POOR", "REJECT"
    )
    assert "growth_potential_score" in result["evaluation"]
    assert "valuation_score" in result["evaluation"]


def test_opportunity_valuation_undervalued():
    engine = OpportunityEvaluationEngine()
    profile = OpportunityProfile(
        symbol="VALUE_CO",
        sector="Financials",
        market_cap=50000000000.0,
        growth_rate=0.05,
        pe_ratio=8.0,
        competitive_moat="moderate",
        risk_score=30.0,
    )
    result = engine.evaluate(profile)
    assert result["evaluation"]["valuation_level"] == "UNDERVALUED"


def test_ai_investment_committee():
    committee = AIInvestmentCommittee()
    result = committee.discuss("AI Thesis")
    assert result["decision"] == "AI Thesis"


def test_committee_with_thesis():
    committee = AIInvestmentCommittee()
    thesis_data = {
        "symbol": "NVDA",
        "title": "AI Chip Dominance",
        "why_buy": "Dominant AI GPU position with strong moat",
        "why_now": "AI capex cycle accelerating rapidly",
        "catalyst": "New Blackwell architecture launch",
        "risks": ["Competition from AMD", "Cyclical semiconductor market"],
        "exit_conditions": ["AI capex growth slows significantly"],
        "expected_return": 0.30,
    }
    result = committee.discuss(thesis_data)
    decision = result["decision"]
    assert decision["symbol"] == "NVDA"
    assert len(decision["votes"]) == 4  # Bull, Bear, Risk, PM
    assert decision["consensus"] in (
        "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    )
    assert "debate_summary" in decision


def test_bull_case_agent():
    agent = BullCaseAgent()
    result = agent.analyze("NVDA")
    assert result["bull_case"] == "NVDA"


def test_bull_case_with_data():
    agent = BullCaseAgent()
    data = {
        "symbol": "NVDA",
        "thesis": {
            "title": "AI Dominance",
            "why_buy": "Market leader in AI GPU with strong competitive moat",
            "why_now": "AI capex cycle accelerating",
            "catalyst": "Blackwell architecture launch",
            "expected_return": 0.30,
        },
    }
    result = agent.analyze(data)
    bull = result["bull_case"]
    assert bull["symbol"] == "NVDA"
    assert bull["bullish_conviction"] > 0
    assert len(bull["growth_drivers"]) > 0
    assert len(bull["catalysts"]) > 0


def test_bear_case_agent():
    agent = BearCaseAgent()
    result = agent.analyze("NVDA")
    assert result["bear_case"] == "NVDA"


def test_bear_case_with_data():
    agent = BearCaseAgent()
    data = {
        "symbol": "NVDA",
        "thesis": {
            "title": "AI Dominance",
            "why_buy": "Market leader in AI GPU",
            "risks": ["Competition intensifying", "Cyclical downturn", "Valuation compression"],
            "expected_return": 0.30,
        },
    }
    result = agent.analyze(data)
    bear = result["bear_case"]
    assert bear["symbol"] == "NVDA"
    assert bear["risk_intensity"] > 0
    assert len(bear["risk_factors"]) > 0
    assert len(bear["failure_scenarios"]) > 0


def test_conviction_score_engine():
    engine = ConvictionScoreEngine()
    result = engine.score(80)
    assert result["score"] == 80


def test_conviction_with_analysis():
    engine = ConvictionScoreEngine()
    analysis = {
        "symbol": "NVDA",
        "bull_case": {
            "bullish_conviction": 0.75,
            "catalysts": ["New product", "Market expansion"],
            "growth_drivers": ["AI adoption", "Cloud growth", "Edge computing"],
        },
        "bear_case": {
            "risk_intensity": 0.35,
            "risk_factors": ["Competition", "Valuation"],
            "max_drawdown_estimate": 0.15,
        },
        "votes": [
            {"vote": "BUY", "confidence": 0.8},
            {"vote": "BUY", "confidence": 0.7},
            {"vote": "HOLD", "confidence": 0.6},
            {"vote": "STRONG_BUY", "confidence": 0.9},
        ],
    }
    result = engine.score(analysis)
    score_data = result["score"]
    assert score_data["symbol"] == "NVDA"
    assert 0 <= score_data["score"] <= 100
    assert "level" in score_data
    assert "label" in score_data


def test_investment_decision_engine():
    engine = InvestmentDecisionEngine()
    result = engine.decide(85)
    assert result["decision"]["decision"] in (
        "BUY", "STRONG_BUY", "HOLD", "REDUCE", "SELL", "REJECT"
    )


def test_decision_with_high_conviction():
    engine = InvestmentDecisionEngine()
    result = engine.decide({"score": {"score": 88, "symbol": "NVDA"}})
    assert result["decision"]["symbol"] == "NVDA"
    assert result["decision"]["decision"] == "STRONG_BUY"
    assert result["decision"]["position_size_pct"] > 0


def test_decision_with_low_conviction():
    engine = InvestmentDecisionEngine()
    result = engine.decide(15)
    assert result["decision"]["decision"] == "REJECT"
    assert result["decision"]["position_size_pct"] == 0.0


def test_decision_with_moderate_conviction():
    engine = InvestmentDecisionEngine()
    result = engine.decide(55)
    assert result["decision"]["decision"] == "HOLD"


def test_decision_explanation_engine():
    engine = DecisionExplanationEngine()
    result = engine.explain("BUY")
    assert result["explanation"] == "BUY"


def test_explanation_with_decision():
    engine = DecisionExplanationEngine()
    data = {
        "thesis": {
            "why_buy": "Market leader in AI chips",
            "catalyst": "Blackwell architecture launch",
        },
        "bull_case": {
            "bull_case": {
                "catalysts": ["Product launch", "Market expansion"],
            },
        },
        "bear_case": {
            "bear_case": {
                "risk_factors": ["Competition", "Valuation compression"],
                "invalidation_points": ["AI demand slows"],
            },
        },
        "decision": {
            "decision_id": "DEC_0001",
            "symbol": "NVDA",
            "decision": "STRONG_BUY",
            "conviction_score": 88.0,
            "rationale": "Strong conviction supports aggressive entry",
            "risk_controls": ["Hard stop-loss", "Scale in over 3 tranches"],
        },
        "votes": [
            {"vote": "STRONG_BUY"},
            {"vote": "BUY"},
            {"vote": "BUY"},
            {"vote": "STRONG_BUY"},
        ],
    }
    result = engine.explain(data)
    exp = result["explanation"]
    assert exp["symbol"] == "NVDA"
    assert exp["decision"] == "STRONG_BUY"
    assert len(exp["evidence_used"]) > 0
    assert len(exp["risk_considerations"]) > 0
    assert len(exp["what_invalidates"]) > 0
    assert len(exp["alternatives_considered"]) > 0


def test_decision_review_engine():
    engine = DecisionReviewEngine()
    result = engine.review("result")
    assert result["review"] == "result"


def test_review_correct_prediction():
    engine = DecisionReviewEngine()
    data = {
        "decision_id": "DEC_0001",
        "symbol": "NVDA",
        "decision": "STRONG_BUY",
        "predicted_outcome": "Stock up 20% in 6 months",
        "actual_outcome": "Stock up 22% in 6 months",
        "conviction_score": 88.0,
        "thesis": {"why_buy": "AI chip dominance"},
    }
    result = engine.review(data)
    review = result["review"]
    assert review["symbol"] == "NVDA"
    assert review["prediction_correct"] is True
    assert review["outcome"] == "CORRECT"
    assert review["error_source"] == "NONE"
    assert len(review["lessons_learned"]) > 0


def test_review_incorrect_prediction():
    engine = DecisionReviewEngine()
    data = {
        "decision_id": "DEC_0002",
        "symbol": "INTC",
        "decision": "BUY",
        "predicted_outcome": "Stock up 15%",
        "actual_outcome": "Stock down 20%",
        "conviction_score": 72.0,
        "thesis": {"why_buy": "Turnaround story"},
    }
    result = engine.review(data)
    review = result["review"]
    assert review["prediction_correct"] is False
    assert review["error_source"] != "NONE"
    assert len(review["improvement_actions"]) > 0


def test_investment_memory():
    memory = InvestmentDecisionMemory()
    assert memory.history == []
    memory.save({"decision": "BUY NVDA", "result": "profit"})
    memory.save({"decision": "SELL INTC", "result": "avoided loss"})
    assert len(memory.history) == 2
    assert memory.history[0]["decision"] == "BUY NVDA"
    assert memory.history[1]["result"] == "avoided loss"


def test_investment_memory_with_entry():
    memory = InvestmentDecisionMemory()
    entry = InvestmentMemoryEntry(
        entry_id="M001",
        symbol="NVDA",
        thesis="AI chip dominance",
        decision="STRONG_BUY",
        conviction_score=88.0,
        reason="AI demand accelerating",
        outcome="Stock up 25%",
        lesson="Strong thesis with high conviction works well",
        category=DecisionCategory.WIN,
        return_pct=0.25,
    )
    memory.save(entry)
    assert len(memory.history) == 1
    assert len(memory.lessons) == 1
    assert memory.get_win_rate() == 1.0


def test_memory_patterns():
    memory = InvestmentDecisionMemory()
    for i in range(4):
        entry = InvestmentMemoryEntry(
            entry_id=f"M{i:03d}",
            symbol="NVDA",
            thesis="AI growth",
            decision="STRONG_BUY",
            conviction_score=85.0,
            reason="Strong thesis",
            outcome=f"Up {15 + i * 5}%",
            lesson="Good pattern",
            category=DecisionCategory.WIN if i < 3 else DecisionCategory.LOSS,
            return_pct=0.15 + i * 0.05,
        )
        memory.save(entry)

    best = memory.get_best_patterns(min_samples=3)
    assert len(best) > 0

    # Should have knowledge for NVDA
    knowledge = memory.get_institutional_knowledge("NVDA")
    assert knowledge["decisions_count"] == 4
    assert knowledge["win_count"] == 3


def test_investment_decision_service():
    committee = AIInvestmentCommittee()
    service = InvestmentDecisionService(committee=committee)
    result = service.decide("AI Thesis")
    assert result["decision"] == "AI Thesis"


def test_full_investment_decision_workflow():
    """End-to-end autonomous investment decision workflow."""

    # 1. Investment Thesis Generation
    thesis_engine = InvestmentThesisGenerator()
    thesis = InvestmentThesis(
        thesis_id="T001",
        symbol="NVDA",
        thesis_type=ThesisType.GROWTH,
        title="AI Semiconductor Dominance",
        why_buy="Dominant position in AI GPU market with strong moat",
        why_now="AI capex cycle accelerating rapidly across cloud and enterprise",
        catalyst="Blackwell architecture launch in Q4 2026",
        risks=["Competition from AMD", "Cyclical semiconductor risk", "Export controls"],
        exit_conditions=["AI capex growth slows >20%", "Market share declines >5%"],
        expected_return=0.30,
        time_horizon="12M",
        confidence=ThesisConfidence.HIGH,
    )
    result = thesis_engine.generate(thesis)
    assert result["thesis"]["thesis_id"] == "T001"

    # 2. Opportunity Evaluation
    opp_engine = OpportunityEvaluationEngine()
    profile = OpportunityProfile(
        symbol="NVDA", sector="Technology", market_cap=1000000000000.0,
        growth_rate=0.25, pe_ratio=35.0, competitive_moat="strong",
        risk_score=40.0, market_opportunity="AI infrastructure",
    )
    evaluation = opp_engine.evaluate(profile)
    assert evaluation["evaluation"]["symbol"] == "NVDA"

    # 3. Bull Case Analysis
    bull_agent = BullCaseAgent()
    bull_case = bull_agent.analyze({
        "symbol": "NVDA",
        "thesis": {
            "title": "AI Dominance",
            "why_buy": "Market leader with strong competitive moat",
            "why_now": "AI capex accelerating",
            "catalyst": "Blackwell launch",
            "expected_return": 0.30,
        },
    })
    assert bull_case["bull_case"]["symbol"] == "NVDA"

    # 4. Bear Case Analysis
    bear_agent = BearCaseAgent()
    bear_case = bear_agent.analyze({
        "symbol": "NVDA",
        "thesis": {
            "title": "AI Dominance",
            "risks": ["Competition", "Valuation", "Cyclical"],
            "expected_return": 0.30,
        },
    })
    assert bear_case["bear_case"]["symbol"] == "NVDA"

    # 5. AI Investment Committee
    committee = AIInvestmentCommittee()
    committee_result = committee.discuss({
        "symbol": "NVDA",
        "title": "AI Semiconductor Dominance",
        "why_buy": "Dominant AI GPU position",
        "why_now": "AI capex accelerating",
        "catalyst": "Blackwell architecture launch",
        "risks": ["Competition from AMD", "Cyclical risk"],
        "exit_conditions": ["AI capex growth slows"],
        "expected_return": 0.30,
    })
    assert len(committee_result["decision"]["votes"]) == 4

    # 6. Conviction Scoring
    conviction_engine = ConvictionScoreEngine()
    conviction = conviction_engine.score({
        "symbol": "NVDA",
        "bull_case": {"bullish_conviction": 0.75, "catalysts": ["Product launch"]},
        "bear_case": {"risk_intensity": 0.35, "risk_factors": ["Competition"]},
        "votes": [{"vote": "BUY"}, {"vote": "STRONG_BUY"}, {"vote": "BUY"}, {"vote": "BUY"}],
    })
    assert 0 <= conviction["score"]["score"] <= 100

    # 7. Investment Decision
    decision_engine = InvestmentDecisionEngine()
    decision = decision_engine.decide(conviction)
    assert decision["decision"]["decision"] in (
        "STRONG_BUY", "BUY", "HOLD", "REDUCE", "SELL", "REJECT"
    )

    # 8. Decision Explanation
    explanation_engine = DecisionExplanationEngine()
    explanation = explanation_engine.explain({
        "thesis": {"why_buy": "AI chip dominance", "catalyst": "Blackwell launch"},
        "bull_case": {"bull_case": {"catalysts": ["Product launch"]}},
        "bear_case": {"bear_case": {"risk_factors": ["Competition"]}},
        "decision": decision["decision"],
        "votes": [{"vote": "BUY"}, {"vote": "STRONG_BUY"}],
    })
    assert explanation["explanation"]["symbol"] == decision["decision"]["symbol"]

    # 9. Decision Review
    review_engine = DecisionReviewEngine()
    review = review_engine.review({
        "decision_id": decision["decision"]["decision_id"],
        "symbol": "NVDA",
        "decision": decision["decision"]["decision"],
        "predicted_outcome": "Stock up 20%+",
        "actual_outcome": "Stock up 25%",
        "conviction_score": conviction["score"]["score"],
        "thesis": {"why_buy": "AI chip dominance"},
    })
    assert review["review"]["prediction_correct"] is True

    # 10. Investment Memory
    memory = InvestmentDecisionMemory()
    memory.save(InvestmentMemoryEntry(
        entry_id="M001", symbol="NVDA", thesis="AI chip dominance",
        decision="STRONG_BUY", conviction_score=88.0,
        reason="Strong thesis with high conviction",
        outcome="Stock up 25%", lesson="Strong conviction on dominant thesis works",
        category=DecisionCategory.WIN, return_pct=0.25,
    ))
    assert len(memory.history) == 1
    assert memory.get_win_rate() == 1.0

    # 11. Investment Decision Service
    service = InvestmentDecisionService(committee=committee)
    result = service.decide("NVDA Thesis")
    assert result is not None
