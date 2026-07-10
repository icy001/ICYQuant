import pytest
from datetime import date

from research.experiments.metadata import ExperimentMetadata
from research.experiments.experiment import Experiment
from research.experiments.registry import ExperimentRegistry


class TestExperimentMetadata:

    def test_metadata_creation(self):
        metadata = ExperimentMetadata(
            name="test_exp",
            strategy="MovingAverageCross",
            symbols=["NVDA", "GLD"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
            parameters={"short": 10, "long": 60}
        )
        assert metadata.name == "test_exp"
        assert metadata.strategy == "MovingAverageCross"
        assert metadata.symbols == ["NVDA", "GLD"]
        assert metadata.start == date(2020, 1, 1)
        assert metadata.end == date(2025, 1, 1)
        assert metadata.parameters == {"short": 10, "long": 60}

    def test_metadata_without_parameters(self):
        metadata = ExperimentMetadata(
            name="test_exp",
            strategy="BuyAndHold",
            symbols=["NVDA"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        assert metadata.parameters is None


class TestExperiment:

    def test_experiment_creation(self):
        metadata = ExperimentMetadata(
            name="test_exp",
            strategy="MovingAverageCross",
            symbols=["NVDA"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        exp = Experiment(metadata=metadata)
        assert exp.metadata == metadata
        assert exp.result is None

    def test_experiment_complete(self):
        metadata = ExperimentMetadata(
            name="test_exp",
            strategy="MovingAverageCross",
            symbols=["NVDA"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        exp = Experiment(metadata=metadata)
        result = {"return": 0.25, "sharpe": 1.8, "drawdown": 0.09}
        exp.complete(result)
        assert exp.result == result


class TestExperimentRegistry:

    def test_registry_initialization(self):
        registry = ExperimentRegistry()
        assert len(registry) == 0

    def test_register_experiment(self):
        registry = ExperimentRegistry()
        
        metadata = ExperimentMetadata(
            name="test_exp",
            strategy="MovingAverageCross",
            symbols=["NVDA"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        exp = Experiment(metadata=metadata)
        
        registry.register(exp)
        
        assert len(registry.list_all()) == 1
        assert registry.list_all()[0] == exp

    def test_register_multiple_experiments(self):
        registry = ExperimentRegistry()
        
        metadata1 = ExperimentMetadata(
            name="exp1",
            strategy="Strategy1",
            symbols=["NVDA"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        metadata2 = ExperimentMetadata(
            name="exp2",
            strategy="Strategy2",
            symbols=["GLD"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        
        registry.register(Experiment(metadata=metadata1))
        registry.register(Experiment(metadata=metadata2))
        
        assert len(registry) == 2

    def test_get_by_name(self):
        registry = ExperimentRegistry()
        
        metadata = ExperimentMetadata(
            name="NVDA_AI_Portfolio",
            strategy="MovingAverageCross",
            symbols=["NVDA", "GLD"],
            start=date(2020, 1, 1),
            end=date(2025, 1, 1),
        )
        exp = Experiment(metadata=metadata)
        registry.register(exp)
        
        found = registry.get_by_name("NVDA_AI_Portfolio")
        assert found == exp

    def test_get_by_name_not_found(self):
        registry = ExperimentRegistry()
        assert registry.get_by_name("nonexistent") is None