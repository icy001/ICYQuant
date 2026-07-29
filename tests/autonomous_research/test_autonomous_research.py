from services.autonomous_research import *


def test_research_detector():
    agent = ResearchOpportunityDetector()
    result = agent.detect("AI Semiconductor")
    assert result["opportunity"] == "AI Semiconductor"


def test_hypothesis_generator():
    generator = HypothesisGenerator()
    result = generator.generate("HBM_memory_cycle")
    assert result == {"hypothesis": "HBM_memory_cycle"}


def test_experiment_planner():
    planner = ExperimentPlanner()
    result = planner.plan("momentum_factor_analysis")
    assert result == {"experiment": "momentum_factor_analysis"}


def test_research_data_agent():
    agent = ResearchDataAgent()
    result = agent.prepare("market_data_2024")
    assert result == {"data": "market_data_2024"}


def test_backtest_execution_agent():
    agent = BacktestExecutionAgent()
    result = agent.run("mean_reversion_strategy")
    assert result == {"result": "mean_reversion_strategy"}


def test_research_evaluation_engine():
    evaluator = ResearchEvaluationEngine()
    result = evaluator.evaluate({"sharpe": 1.8, "drawdown": 0.12})
    assert result == {"score": 100}


def test_research_critic_agent():
    critic = ResearchCriticAgent()
    result = critic.review({"strategy": "momentum", "sharpe": 2.0})
    assert result == {"review": {"strategy": "momentum", "sharpe": 2.0}}


def test_research_report_generator():
    generator = ResearchReportGenerator()
    result = generator.generate({"research": "AI_factor_discovery"})
    assert result == {"report": {"research": "AI_factor_discovery"}}


def test_autonomous_research_scheduler():
    scheduler = AutonomousResearchScheduler()
    result = scheduler.schedule("daily_market_scan")
    assert result == {"task": "daily_market_scan"}


def test_research_loop_memory():
    memory = ResearchLoopMemory()
    assert memory.history == []
    memory.save({"cycle": 1, "opportunity": "AI_semiconductor"})
    memory.save({"cycle": 2, "hypothesis": "HBM_momentum"})
    assert len(memory.history) == 2
    assert memory.history[0]["cycle"] == 1
    assert memory.history[1]["hypothesis"] == "HBM_momentum"


def test_autonomous_research_service():
    detector = ResearchOpportunityDetector()
    service = AutonomousResearchService(detector=detector)
    result = service.discover("market_anomaly_scan")
    assert result == {"opportunity": "market_anomaly_scan"}


def test_full_autonomous_research_loop():
    """End-to-end autonomous research loop workflow."""
    # 1. Detect opportunity
    detector = ResearchOpportunityDetector()
    opp = detector.detect("AI_data_center_capex_surge")
    assert opp["opportunity"] == "AI_data_center_capex_surge"

    # 2. Generate hypothesis
    hypothesis_gen = HypothesisGenerator()
    hypothesis = hypothesis_gen.generate("HBM_stocks_outperform_during_capex_phase2")
    assert hypothesis["hypothesis"] == "HBM_stocks_outperform_during_capex_phase2"

    # 3. Plan experiment
    planner = ExperimentPlanner()
    experiment = planner.plan(hypothesis["hypothesis"])
    assert experiment["experiment"] == "HBM_stocks_outperform_during_capex_phase2"

    # 4. Prepare data
    data_agent = ResearchDataAgent()
    data = data_agent.prepare("HBM_equity_universe_2023_2025")
    assert data["data"] == "HBM_equity_universe_2023_2025"

    # 5. Run backtest
    backtest = BacktestExecutionAgent()
    bt_result = backtest.run("HBM_momentum_factor")
    assert bt_result["result"] == "HBM_momentum_factor"

    # 6. Evaluate results
    evaluator = ResearchEvaluationEngine()
    score = evaluator.evaluate(bt_result)
    assert score["score"] == 100

    # 7. Critic review
    critic = ResearchCriticAgent()
    review = critic.review({
        "strategy": "HBM_momentum",
        "sharpe": 2.1,
        "max_drawdown": 0.08,
    })
    assert review["review"]["strategy"] == "HBM_momentum"

    # 8. Generate report
    report_gen = ResearchReportGenerator()
    report = report_gen.generate({
        "title": "HBM Momentum Factor Research",
        "conclusion": "Positive alpha observed in AI CapEx Phase 2",
    })
    assert report["report"]["title"] == "HBM Momentum Factor Research"

    # 9. Schedule next run
    scheduler = AutonomousResearchScheduler()
    next_task = scheduler.schedule("tomorrow_0900_market_scan")
    assert next_task["task"] == "tomorrow_0900_market_scan"

    # 10. Save to research memory
    memory = ResearchLoopMemory()
    memory.save({"cycle": 1, "status": "completed", "finding": "HBM_momentum_valid"})
    assert len(memory.history) == 1

    # 11. Autonomous research service
    service = AutonomousResearchService(detector=detector)
    svc_result = service.discover("sector_rotation_anomaly")
    assert svc_result["opportunity"] == "sector_rotation_anomaly"
