"""Tests for AI Autonomous Research Scientist Engine."""

import sys
sys.path.insert(0, "d:/PycharmProjects/ICYQuant")

from services.research_scientist import *


# ============================================================
# Scientist Agent Tests
# ============================================================

def test_scientist_creation():
    agent = ResearchScientistAgent()
    assert agent.name == "ResearchScientist"
    assert agent.domain == ResearchDomain.FACTOR
    assert len(agent.active_projects) == 0


def test_scientist_custom_domain():
    agent = ResearchScientistAgent(name="MacroScientist", domain=ResearchDomain.MACRO)
    assert agent.name == "MacroScientist"
    assert agent.domain == ResearchDomain.MACRO


def test_initiate_research():
    agent = ResearchScientistAgent()
    result = agent.research("AI chips")
    assert "project_id" in result
    assert result["question"] == "AI chips"
    assert result["status"] == "proposed"


def test_initiate_research_returns_project_id():
    agent = ResearchScientistAgent()
    result = agent.initiate_research("Why are AI stocks rising?")
    assert result["project_id"] in agent.active_projects
    assert result["status"] == "proposed"


def test_decompose_question():
    agent = ResearchScientistAgent()
    project = agent.initiate_research("AI chips impact on semiconductors")
    result = agent.decompose_question(project["project_id"], "AI chips impact on semiconductors")
    assert "sub_questions" in result
    assert result["count"] > 0
    assert result["status"] == "hypothesis_formed"


def test_decompose_question_invalid_project():
    agent = ResearchScientistAgent()
    result = agent.decompose_question("nonexistent", "test")
    assert "error" in result


def test_get_active_projects():
    agent = ResearchScientistAgent()
    agent.initiate_research("Test 1")
    agent.initiate_research("Test 2")
    projects = agent.get_active_projects()
    assert len(projects) == 2


def test_get_project():
    agent = ResearchScientistAgent()
    result = agent.initiate_research("Test project")
    project = agent.get_project(result["project_id"])
    assert project is not None
    assert project["title"] == "Test project"


def test_get_project_not_found():
    agent = ResearchScientistAgent()
    project = agent.get_project("nonexistent")
    assert project is None


def test_update_project_status():
    agent = ResearchScientistAgent()
    result = agent.initiate_research("Test status update")
    update = agent.update_project_status(result["project_id"], ResearchStatus.COMPLETED)
    assert update["status"] == "completed"


def test_complete_project_moves_to_completed():
    agent = ResearchScientistAgent()
    result = agent.initiate_research("Test completion")
    agent.update_project_status(result["project_id"], ResearchStatus.COMPLETED)
    assert result["project_id"] not in agent.active_projects
    assert result["project_id"] in agent.completed_projects


def test_reject_project_moves_to_completed():
    agent = ResearchScientistAgent()
    result = agent.initiate_research("Test rejection")
    agent.update_project_status(result["project_id"], ResearchStatus.REJECTED)
    assert result["project_id"] not in agent.active_projects


def test_get_research_summary():
    agent = ResearchScientistAgent()
    agent.initiate_research("Test 1")
    agent.initiate_research("Test 2")
    summary = agent.get_research_summary()
    assert summary["active"] == 2
    assert summary["total_projects"] == 2


def test_research_domains_enum():
    assert ResearchDomain.MACRO.value == "macro"
    assert ResearchDomain.FACTOR.value == "factor"
    assert ResearchDomain.STRATEGY.value == "strategy"


def test_research_question_dataclass():
    rq = ResearchQuestion(question="Test question", domain=ResearchDomain.MACRO)
    d = rq.to_dict()
    assert d["question"] == "Test question"
    assert d["domain"] == "macro"
    assert "id" in d


def test_research_project_dataclass():
    rp = ResearchProject(title="Test Project", domain=ResearchDomain.FACTOR)
    d = rp.to_dict()
    assert d["title"] == "Test Project"
    assert d["status"] == "proposed"


# ============================================================
# Hypothesis Generator Tests
# ============================================================

def test_hypothesis_generator_creation():
    gen = HypothesisGenerator()
    assert len(gen.hypotheses) == 0


def test_generate_hypothesis():
    gen = HypothesisGenerator()
    result = gen.generate("AI CapEx cycle drives semiconductor outperformance")
    assert "id" in result
    assert "statement" in result
    assert "type" in result


def test_generate_hypothesis_returns_dict():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("momentum factor predicts future returns")
    assert h.statement != ""
    assert h.hypothesis_type is not None
    assert len(h.variables) > 0
    assert h.test_method != ""
    assert len(h.evaluation_metrics) > 0


def test_hypothesis_type_inference():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("momentum factor works")
    assert h.hypothesis_type == HypothesisType.FACTOR

    h2 = gen.generate_hypothesis("predict stock returns with ML")
    assert h2.hypothesis_type == HypothesisType.PREDICTIVE


def test_hypothesis_null_statement():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("value factor outperforms")
    assert "false" in h.null_statement.lower()


def test_generate_batch():
    gen = HypothesisGenerator()
    results = gen.generate_batch("momentum strategy", count=3)
    assert len(results) == 3
    assert all("id" in r for r in results)


def test_refine_hypothesis():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("momentum works")
    refined = gen.refine_hypothesis(h.id, "momentum works in bull markets")
    assert refined is not None
    assert "REFINED" in refined["statement"]


def test_refine_nonexistent():
    gen = HypothesisGenerator()
    result = gen.refine_hypothesis("nonexistent", "new idea")
    assert result is None


def test_evaluate_hypothesis():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("test hypothesis")
    result = gen.evaluate_hypothesis(h.id, {"p_value": 0.001, "effect_size": 0.5})
    assert result is not None
    assert result["status"] == "confirmed"


def test_evaluate_hypothesis_rejected():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("test hypothesis")
    result = gen.evaluate_hypothesis(h.id, {"p_value": 0.5, "effect_size": 0.01})
    assert result["status"] == "rejected"


def test_get_hypothesis():
    gen = HypothesisGenerator()
    h = gen.generate_hypothesis("test")
    found = gen.get_hypothesis(h.id)
    assert found is not None


def test_list_hypotheses():
    gen = HypothesisGenerator()
    gen.generate_hypothesis("test 1")
    gen.generate_hypothesis("test 2")
    hypotheses = gen.list_hypotheses()
    assert len(hypotheses) == 2


def test_get_hypothesis_summary():
    gen = HypothesisGenerator()
    gen.generate_hypothesis("test")
    summary = gen.get_summary()
    assert summary["total_hypotheses"] == 1


# ============================================================
# Research Question Engine Tests
# ============================================================

def test_question_engine_creation():
    engine = ResearchQuestionEngine()
    assert len(engine.analyzed_questions) == 0


def test_analyze_question():
    engine = ResearchQuestionEngine()
    result = engine.analyze("Why are AI stocks rising?")
    assert result["original_question"] == "Why are AI stocks rising?"
    assert "category" in result
    assert "sub_questions" in result


def test_analyze_returns_category():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("Why are AI stocks rising?")
    assert analysis.category == QuestionCategory.CAUSAL


def test_analyze_predictive():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("predict stock returns next month")
    assert analysis.category == QuestionCategory.PREDICTIVE


def test_question_complexity():
    engine = ResearchQuestionEngine()
    simple = engine.analyze_question("What is the return?")
    assert simple.complexity in (QuestionComplexity.SIMPLE, QuestionComplexity.MODERATE)


def test_decompose_sub_questions():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("Why do momentum factors work?")
    assert len(analysis.sub_questions) > 0
    for sq in analysis.sub_questions:
        assert "dimension" in sq
        assert "question" in sq


def test_assumptions_extracted():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("What factors predict returns?")
    assert len(analysis.assumptions) > 0


def test_methodology_suggestions():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("What factors predict returns?")
    assert len(analysis.methodology_suggestions) > 0


def test_data_requirements():
    engine = ResearchQuestionEngine()
    analysis = engine.analyze_question("market returns analysis")
    assert len(analysis.data_requirements) > 0


def test_get_analysis():
    engine = ResearchQuestionEngine()
    result = engine.analyze("test question")
    found = engine.get_analysis(result["id"])
    assert found is not None
    assert found["original_question"] == "test question"


def test_question_summary():
    engine = ResearchQuestionEngine()
    engine.analyze("test 1")
    engine.analyze("test 2")
    summary = engine.get_summary()
    assert summary["total_analyzed"] == 2


# ============================================================
# Experiment Design Engine Tests
# ============================================================

def test_experiment_engine_creation():
    engine = ExperimentDesignEngine()
    assert len(engine.experiments) == 0


def test_design_experiment():
    engine = ExperimentDesignEngine()
    result = engine.design({"statement": "momentum factor works", "type": "factor"})
    assert "id" in result
    assert "type" in result
    assert "name" in result


def test_design_experiment_full():
    engine = ExperimentDesignEngine()
    exp = engine.design_experiment({"statement": "momentum factor works", "type": "factor", "id": "h1"})
    assert exp.hypothesis_id == "h1"
    assert exp.experiment_type is not None
    assert len(exp.methodology["steps"]) > 0
    assert len(exp.evaluation_metrics) > 0
    assert len(exp.controls) > 0


def test_experiment_type_selection():
    engine = ExperimentDesignEngine()
    exp = engine.design_experiment({"statement": "test", "type": "strategy"})
    assert exp.experiment_type == ExperimentType.BACKTEST

    exp2 = engine.design_experiment({"statement": "test", "type": "factor"})
    assert exp2.experiment_type == ExperimentType.CROSS_VALIDATION


def test_run_experiment():
    engine = ExperimentDesignEngine()
    exp = engine.design_experiment({"statement": "test", "type": "factor", "id": "h1"})
    result = engine.run_experiment(exp.id)
    assert result is not None
    assert result["status"] == "running"


def test_complete_experiment():
    engine = ExperimentDesignEngine()
    exp = engine.design_experiment({"statement": "test", "type": "factor", "id": "h1"})
    engine.run_experiment(exp.id)
    result = engine.complete_experiment(exp.id, {"p_value": 0.01})
    assert result is not None
    assert result["status"] == "completed"


def test_get_experiment():
    engine = ExperimentDesignEngine()
    exp = engine.design_experiment({"statement": "test", "type": "factor", "id": "h1"})
    found = engine.get_experiment(exp.id)
    assert found is not None


def test_list_experiments():
    engine = ExperimentDesignEngine()
    engine.design_experiment({"statement": "test 1", "type": "factor", "id": "h1"})
    engine.design_experiment({"statement": "test 2", "type": "factor", "id": "h2"})
    experiments = engine.list_experiments()
    assert len(experiments) == 2


def test_experiment_summary():
    engine = ExperimentDesignEngine()
    engine.design_experiment({"statement": "test", "type": "factor", "id": "h1"})
    summary = engine.get_summary()
    assert summary["total_experiments"] == 1


# ============================================================
# Data Investigation Engine Tests
# ============================================================

def test_data_engine_creation():
    engine = DataInvestigationEngine()
    assert len(engine.profiles) == 0


def test_investigate_dataset():
    engine = DataInvestigationEngine()
    result = engine.investigate({"name": "market_data", "type": "market"})
    assert "id" in result
    assert "quality" in result
    assert "dataset_name" in result


def test_investigate_full_profile():
    engine = DataInvestigationEngine()
    profile = engine.investigate_dataset({
        "name": "test_data",
        "type": "market",
        "rows": 5000,
        "columns_count": 15,
    })
    assert profile.dataset_name == "test_data"
    assert profile.source == DataSource.MARKET
    assert profile.row_count == 5000
    assert profile.column_count == 15


def test_data_quality_excellent():
    engine = DataInvestigationEngine()
    profile = engine.investigate_dataset({
        "name": "clean_data",
        "type": "market",
        "missing_rate": 0.005,
        "anomalies": [],
    })
    assert profile.quality == DataQuality.EXCELLENT


def test_data_quality_poor():
    engine = DataInvestigationEngine()
    profile = engine.investigate_dataset({
        "name": "dirty_data",
        "type": "market",
        "missing_rate": 0.2,
    })
    assert profile.quality == DataQuality.POOR


def test_get_profile():
    engine = DataInvestigationEngine()
    result = engine.investigate({"name": "test", "type": "market"})
    profile = engine.get_profile(result["id"])
    assert profile is not None


def test_data_summary():
    engine = DataInvestigationEngine()
    engine.investigate({"name": "d1", "type": "market", "missing_rate": 0.01})
    engine.investigate({"name": "d2", "type": "fundamental", "missing_rate": 0.1})
    summary = engine.get_summary()
    assert summary["total_datasets"] == 2


# ============================================================
# Quant Discovery Engine Tests
# ============================================================

def test_discovery_engine_creation():
    engine = QuantDiscoveryEngine()
    assert len(engine.discoveries) == 0


def test_discover_alpha():
    engine = QuantDiscoveryEngine()
    result = engine.discover({"name": "market_data", "type": "factor"})
    assert "id" in result
    assert "sharpe" in result
    assert "name" in result


def test_discover_factor():
    engine = QuantDiscoveryEngine()
    discovery = engine.run_discovery({"name": "price_data", "type": "factor"})
    assert discovery.discovery_type == DiscoveryType.FACTOR
    assert discovery.sharpe > 0
    assert discovery.name.startswith("Factor")


def test_discover_signal():
    engine = QuantDiscoveryEngine()
    discovery = engine.run_discovery({"name": "volume_data", "type": "signal"})
    assert discovery.discovery_type == DiscoveryType.SIGNAL


def test_validate_discovery_confirmed():
    engine = QuantDiscoveryEngine()
    d = engine.run_discovery({"name": "good_data", "type": "factor"})
    d.sharpe = 0.9
    d.ic_mean = 0.05
    result = engine.validate_discovery(d.id)
    assert result["status"] == "confirmed"


def test_validate_discovery_decayed():
    engine = QuantDiscoveryEngine()
    d = engine.run_discovery({"name": "bad_data", "type": "factor"})
    d.sharpe = 0.2
    d.ic_mean = 0.01
    result = engine.validate_discovery(d.id)
    assert result["status"] == "decayed"


def test_rank_discoveries():
    engine = QuantDiscoveryEngine()
    engine.run_discovery({"name": "d1", "type": "factor"})
    engine.run_discovery({"name": "d2", "type": "signal"})
    ranked = engine.rank_discoveries()
    assert len(ranked) == 2
    assert "score" in ranked[0]


def test_get_discovery():
    engine = QuantDiscoveryEngine()
    d = engine.run_discovery({"name": "test", "type": "factor"})
    found = engine.get_discovery(d.id)
    assert found is not None


def test_discovery_summary():
    engine = QuantDiscoveryEngine()
    engine.run_discovery({"name": "test", "type": "factor"})
    summary = engine.get_summary()
    assert summary["total_discoveries"] == 1


# ============================================================
# Automatic Backtesting Engine Tests
# ============================================================

def test_backtest_engine_creation():
    engine = AutomaticBacktestingEngine()
    assert len(engine.results) == 0


def test_run_backtest():
    engine = AutomaticBacktestingEngine()
    result = engine.run({"name": "momentum_strategy", "type": "quantitative"})
    assert "id" in result
    assert "sharpe_ratio" in result
    assert "strategy_name" in result


def test_backtest_metrics():
    engine = AutomaticBacktestingEngine()
    bt = engine.run_backtest({"name": "test_strategy", "quality": 0.8})
    assert bt.sharpe_ratio > 0
    assert bt.annual_return is not None
    assert bt.max_drawdown < 0
    assert 0 < bt.win_rate < 1


def test_backtest_high_quality():
    engine = AutomaticBacktestingEngine()
    bt = engine.run_backtest({"name": "excellent", "quality": 0.95})
    assert bt.sharpe_ratio > 0.5
    assert bt.win_rate > 0.5


def test_backtest_low_quality():
    engine = AutomaticBacktestingEngine()
    bt = engine.run_backtest({"name": "poor", "quality": 0.3})
    assert bt.sharpe_ratio < 0.5


def test_get_result():
    engine = AutomaticBacktestingEngine()
    bt = engine.run_backtest({"name": "test"})
    found = engine.get_result(bt.id)
    assert found is not None
    assert found["strategy_name"] == "test"


def test_get_best_strategies():
    engine = AutomaticBacktestingEngine()
    engine.run_backtest({"name": "strat_1", "quality": 0.5})
    engine.run_backtest({"name": "strat_2", "quality": 0.9})
    best = engine.get_best_strategies(top_n=1)
    assert len(best) == 1
    assert best[0]["strategy"] == "strat_2"


def test_backtest_summary():
    engine = AutomaticBacktestingEngine()
    engine.run_backtest({"name": "s1", "quality": 0.7})
    engine.run_backtest({"name": "s2", "quality": 0.6})
    summary = engine.get_summary()
    assert summary["total_backtests"] == 2


# ============================================================
# Research Validation Engine Tests
# ============================================================

def test_validation_engine_creation():
    engine = ResearchValidationEngine()
    assert len(engine.reports) == 0


def test_validate_result():
    engine = ResearchValidationEngine()
    result = engine.validate({"strategy_name": "test", "sharpe_ratio": 0.8})
    assert "id" in result
    assert "status" in result
    assert "overall_verdict" in result


def test_validate_strong_strategy():
    engine = ResearchValidationEngine()
    report = engine.validate_result({
        "strategy_name": "strong", "sharpe_ratio": 1.5,
        "max_drawdown": -0.1, "win_rate": 0.6,
    })
    assert report.status in (ValidationStatus.PASSED, ValidationStatus.WARNING)
    assert len(report.validation_methods) == 4


def test_validate_weak_strategy():
    engine = ResearchValidationEngine()
    report = engine.validate_result({
        "strategy_name": "weak", "sharpe_ratio": 0.2,
        "max_drawdown": -0.5, "win_rate": 0.45,
    })
    assert report.status == ValidationStatus.FAILED


def test_validation_warnings():
    engine = ResearchValidationEngine()
    report = engine.validate_result({
        "strategy_name": "test", "sharpe_ratio": 0.3,
    })
    assert len(report.warnings) > 0


def test_validation_recommendations():
    engine = ResearchValidationEngine()
    report = engine.validate_result({
        "strategy_name": "test", "sharpe_ratio": 0.3,
    })
    assert len(report.recommendations) > 0


def test_get_validation_report():
    engine = ResearchValidationEngine()
    result = engine.validate({"strategy_name": "test", "sharpe_ratio": 0.8})
    report = engine.get_report(result["id"])
    assert report is not None
    assert "strategy_name" in report


def test_validation_summary():
    engine = ResearchValidationEngine()
    engine.validate({"strategy_name": "s1", "sharpe_ratio": 1.5})
    engine.validate({"strategy_name": "s2", "sharpe_ratio": 0.2})
    summary = engine.get_summary()
    assert summary["total_validations"] == 2


# ============================================================
# Research Report Generator Tests
# ============================================================

def test_report_generator_creation():
    gen = ResearchReportGenerator()
    assert len(gen.reports) == 0


def test_generate_report():
    gen = ResearchReportGenerator()
    result = gen.generate({"strategy_name": "momentum", "sharpe_ratio": 1.2})
    assert "id" in result
    assert "title" in result
    assert "type" in result


def test_report_sections():
    gen = ResearchReportGenerator()
    report = gen.generate_report({"strategy_name": "momentum", "sharpe_ratio": 1.2})
    assert len(report.sections) >= 3
    assert report.sections[0]["heading"].startswith("1.")


def test_report_abstract():
    gen = ResearchReportGenerator()
    report = gen.generate_report({"strategy_name": "momentum", "sharpe_ratio": 1.2})
    assert len(report.abstract) > 0


def test_report_key_findings():
    gen = ResearchReportGenerator()
    report = gen.generate_report({"strategy_name": "momentum", "sharpe_ratio": 1.2, "win_rate": 0.6})
    assert len(report.key_findings) > 0


def test_publish_report():
    gen = ResearchReportGenerator()
    result = gen.generate({"strategy_name": "test"})
    published = gen.publish_report(result["id"])
    assert published is not None
    assert published["status"] == "published"


def test_get_report():
    gen = ResearchReportGenerator()
    result = gen.generate({"strategy_name": "test"})
    found = gen.get_report(result["id"])
    assert found is not None


def test_report_summary():
    gen = ResearchReportGenerator()
    gen.generate({"strategy_name": "r1"})
    gen.generate({"strategy_name": "r2"})
    summary = gen.get_summary()
    assert summary["total_reports"] == 2


# ============================================================
# Research Memory Tests
# ============================================================

def test_memory_creation():
    memory = ResearchMemory()
    assert len(memory.history) == 0
    assert len(memory.entries) == 0


def test_save_research():
    memory = ResearchMemory()
    result = memory.save({"title": "test research", "type": "hypothesis"})
    assert len(memory.history) == 1
    assert "id" in result


def test_save_entry():
    memory = ResearchMemory()
    entry = memory.save_entry({"title": "test", "type": "hypothesis", "sharpe_ratio": 0.8})
    assert entry.category == MemoryCategory.HYPOTHESIS
    assert entry.title == "test"


def test_save_failure():
    memory = ResearchMemory()
    memory.save_entry({"title": "failed experiment", "type": "failure", "reason": "data issue"})
    assert len(memory.failure_log) == 1


def test_save_insight():
    memory = ResearchMemory()
    memory.save_entry({"title": "important finding", "type": "insight", "sharpe_ratio": 1.5})
    assert len(memory.insights) == 1


def test_search_memory():
    memory = ResearchMemory()
    memory.save_entry({"title": "momentum factor research", "type": "hypothesis"})
    results = memory.search("momentum")
    assert len(results) > 0


def test_get_failures():
    memory = ResearchMemory()
    memory.save_entry({"title": "f1", "type": "failure", "reason": "reason1"})
    memory.save_entry({"title": "f2", "type": "failure", "reason": "reason2"})
    failures = memory.get_failures()
    assert len(failures) == 2


def test_get_insights():
    memory = ResearchMemory()
    memory.save_entry({"title": "insight1", "type": "insight", "sharpe_ratio": 1.5})
    memory.save_entry({"title": "low_value", "type": "insight", "sharpe_ratio": 0.1})
    insights = memory.get_insights(min_importance=0.5)
    assert len(insights) >= 1


def test_memory_summary():
    memory = ResearchMemory()
    memory.save_entry({"title": "t1", "type": "hypothesis"})
    memory.save_entry({"title": "t2", "type": "backtest"})
    summary = memory.get_summary()
    assert summary["total_entries"] == 2


# ============================================================
# Research Scientist Service Tests
# ============================================================

def test_service_creation():
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    assert service.scientist is agent


def test_service_run():
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    result = service.run("Is momentum a valid factor?")
    assert "project_id" in result
    assert len(result["stages"]) > 5
    assert "hypotheses" in result
    assert "backtest" in result
    assert "validation" in result


def test_service_research():
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    result = service.research("Test research question")
    assert result["status"] == "completed"
    assert "summary" in result


def test_service_get_status():
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    status = service.get_status()
    assert "scientist" in status
    assert "hypotheses" in status
    assert "backtests" in status


def test_service_quick_hypothesis_test():
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    result = service.quick_hypothesis_test("momentum factor")
    assert "hypothesis" in result
    assert "sharpe" in result
    assert "validation" in result


def test_service_end_to_end_loop():
    """Full end-to-end research loop test."""
    agent = ResearchScientistAgent()
    service = ResearchScientistService(agent)
    result = service.run("AI CapEx cycle impact on semiconductors")
    assert result["status"] == "completed"
    assert len(result["stages"]) == 10  # All 10 stages completed
    assert "summary" in result


def test_full_imports():
    """Verify all exports are importable."""
    from services.research_scientist import (
        ResearchScientistAgent, HypothesisGenerator, ResearchQuestionEngine,
        ExperimentDesignEngine, DataInvestigationEngine, QuantDiscoveryEngine,
        AutomaticBacktestingEngine, ResearchValidationEngine,
        ResearchReportGenerator, ResearchMemory, ResearchScientistService,
    )
    assert True


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    import traceback

    tests = [
        # Scientist Agent (15)
        test_scientist_creation, test_scientist_custom_domain,
        test_initiate_research, test_initiate_research_returns_project_id,
        test_decompose_question, test_decompose_question_invalid_project,
        test_get_active_projects, test_get_project, test_get_project_not_found,
        test_update_project_status, test_complete_project_moves_to_completed,
        test_reject_project_moves_to_completed, test_get_research_summary,
        test_research_domains_enum, test_research_question_dataclass,
        test_research_project_dataclass,
        # Hypothesis (12)
        test_hypothesis_generator_creation, test_generate_hypothesis,
        test_generate_hypothesis_returns_dict, test_hypothesis_type_inference,
        test_hypothesis_null_statement, test_generate_batch,
        test_refine_hypothesis, test_refine_nonexistent,
        test_evaluate_hypothesis, test_evaluate_hypothesis_rejected,
        test_get_hypothesis, test_list_hypotheses, test_get_hypothesis_summary,
        # Question (9)
        test_question_engine_creation, test_analyze_question,
        test_analyze_returns_category, test_analyze_predictive,
        test_question_complexity, test_decompose_sub_questions,
        test_assumptions_extracted, test_methodology_suggestions,
        test_data_requirements, test_get_analysis, test_question_summary,
        # Experiment (9)
        test_experiment_engine_creation, test_design_experiment,
        test_design_experiment_full, test_experiment_type_selection,
        test_run_experiment, test_complete_experiment,
        test_get_experiment, test_list_experiments, test_experiment_summary,
        # Data (7)
        test_data_engine_creation, test_investigate_dataset,
        test_investigate_full_profile, test_data_quality_excellent,
        test_data_quality_poor, test_get_profile, test_data_summary,
        # Discovery (8)
        test_discovery_engine_creation, test_discover_alpha,
        test_discover_factor, test_discover_signal,
        test_validate_discovery_confirmed, test_validate_discovery_decayed,
        test_rank_discoveries, test_get_discovery, test_discovery_summary,
        # Backtest (8)
        test_backtest_engine_creation, test_run_backtest,
        test_backtest_metrics, test_backtest_high_quality,
        test_backtest_low_quality, test_get_result,
        test_get_best_strategies, test_backtest_summary,
        # Validation (7)
        test_validation_engine_creation, test_validate_result,
        test_validate_strong_strategy, test_validate_weak_strategy,
        test_validation_warnings, test_validation_recommendations,
        test_get_validation_report, test_validation_summary,
        # Report (7)
        test_report_generator_creation, test_generate_report,
        test_report_sections, test_report_abstract, test_report_key_findings,
        test_publish_report, test_get_report, test_report_summary,
        # Memory (9)
        test_memory_creation, test_save_research, test_save_entry,
        test_save_failure, test_save_insight, test_search_memory,
        test_get_failures, test_get_insights, test_memory_summary,
        # Service (5)
        test_service_creation, test_service_run, test_service_research,
        test_service_get_status, test_service_quick_hypothesis_test,
        test_service_end_to_end_loop,
        # Full imports
        test_full_imports,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"FAIL: {test.__name__}")
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    if failed > 0:
        sys.exit(1)
