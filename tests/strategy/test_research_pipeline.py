from services.strategy.research import (
    ExperimentStore,
    Experiment,
    ParameterSet,
    ResearchResult,
    PromotionController,
    ResearchPipeline,
)


def test_experiment_store():
    store = ExperimentStore()

    exp = Experiment(
        experiment_id="001",
        strategy_id="momentum",
        version="v1",
        description="test",
    )

    store.save(exp)

    assert len(store.list()) == 1


def test_parameter_set():
    params = ParameterSet(
        name="momentum_v3",
        values={"period": 20, "threshold": 0.5},
    )

    assert params.name == "momentum_v3"
    assert params.values["period"] == 20


def test_research_result():
    result = ResearchResult(
        sharpe=2.0,
        max_drawdown=0.15,
        passed=True,
    )

    assert result.sharpe == 2.0
    assert result.passed is True


def test_promotion_approved():
    controller = PromotionController()
    result = ResearchResult(sharpe=2.0, max_drawdown=0.15, passed=True)

    decision = controller.promote(result)

    assert decision == "APPROVED"


def test_promotion_rejected():
    controller = PromotionController()
    result = ResearchResult(sharpe=0.3, max_drawdown=0.25, passed=False)

    decision = controller.promote(result)

    assert decision == "REJECTED"


def test_research_pipeline():
    class MockBacktest:
        def run(self, experiment):
            return ResearchResult(sharpe=1.8, max_drawdown=0.12, passed=True)

    pipeline = ResearchPipeline()
    exp = Experiment("EXP001", "momentum", "v1", "test")

    result = pipeline.run(exp, MockBacktest())

    assert result.passed is True
    assert result.sharpe == 1.8