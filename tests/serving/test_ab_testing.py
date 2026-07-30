"""Tests for A/B Testing."""
import pytest
from services.serving.ab_testing import (
    ABTesting, ABConfig, ABVariant, ABExperiment, ABStatus, ABResult,
)


class TestABVariant:
    def test_create_variant(self):
        v = ABVariant(name="champion", model_name="alpha_v37", traffic_share=0.9)
        assert v.name == "champion"
        assert v.traffic_share == 0.9


class TestABTesting:
    def test_create_experiment(self):
        ab = ABTesting(ABConfig())
        exp = ab.create_experiment("test_exp", [
            ABVariant("A", "model_a", 0.7),
            ABVariant("B", "model_b", 0.3),
        ])
        assert exp.status == ABStatus.DRAFT
        assert len(exp.variants) == 2
        assert exp.experiment_id != ""

    def test_traffic_sum_validation(self):
        ab = ABTesting(ABConfig())
        with pytest.raises(ValueError, match="sum to 1"):
            ab.create_experiment("bad", [
                ABVariant("A", "m_a", 0.5),
                ABVariant("B", "m_b", 0.3),
            ])

    def test_start_experiment(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 1.0)])
        ab.start("exp1")
        exp = ab.get_experiment("exp1")
        assert exp.status == ABStatus.RUNNING
        assert exp.started_at is not None

    def test_select_variant_consistent_hashing(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [
            ABVariant("A", "m_a", 0.5),
            ABVariant("B", "m_b", 0.5),
        ])
        ab.start("exp1")
        # Same symbol should always go to same variant
        v1 = ab.select_variant("NVDA", "exp1")
        v2 = ab.select_variant("NVDA", "exp1")
        assert v1.name == v2.name

    def test_select_variant_distribution(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [
            ABVariant("A", "m_a", 0.9),
            ABVariant("B", "m_b", 0.1),
        ])
        ab.start("exp1")
        # Test many symbols and check distribution
        counts = {"A": 0, "B": 0}
        for i in range(1000):
            v = ab.select_variant(f"SYM_{i}", "exp1")
            counts[v.name] += 1
        # Should be roughly 90/10 (allow 15% tolerance)
        assert counts["A"] > 750  # 900 - reasonable margin
        assert counts["B"] > 0

    def test_pause_experiment(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 1.0)])
        ab.start("exp1")
        ab.pause("exp1")
        assert ab.get_experiment("exp1").status == ABStatus.PAUSED

    def test_complete_experiment(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 0.6), ABVariant("B", "m_b", 0.4)])
        ab.start("exp1")
        result = ab.complete("exp1", winner="A")
        assert result["winner"] == "A"
        assert ab.get_experiment("exp1").status == ABStatus.COMPLETED

    def test_record_prediction(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 0.5), ABVariant("B", "m_b", 0.5)])
        ab.start("exp1")
        ab.record_prediction("exp1", "A", "NVDA", 0.82, 0.93, latency_ms=12.0)
        ab.record_prediction("exp1", "A", "AAPL", 0.71, 0.88, latency_ms=10.0)
        results = ab.get_results("exp1")
        assert results["A"].prediction_count == 2
        assert 0.7 < results["A"].avg_prediction < 0.9

    def test_get_results_initial(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 0.5), ABVariant("B", "m_b", 0.5)])
        results = ab.get_results("exp1")
        assert results["A"].prediction_count == 0
        assert results["B"].prediction_count == 0

    def test_list_experiments(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("e1", [ABVariant("A", "m_a", 1.0)])
        ab.create_experiment("e2", [ABVariant("B", "m_b", 1.0)])
        exps = ab.list_experiments()
        assert len(exps) == 2

    def test_delete_experiment(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("e1", [ABVariant("A", "m_a", 1.0)])
        assert ab.delete_experiment("e1") is True
        assert ab.get_experiment("e1") is None
        assert ab.delete_experiment("nonexistent") is False

    def test_abresult_to_dict(self):
        r = ABResult(variant_name="test", prediction_count=100, avg_prediction=0.75)
        d = r.to_dict()
        assert d["variant_name"] == "test"
        assert d["prediction_count"] == 100

    def test_not_running_experiment_select(self):
        ab = ABTesting(ABConfig())
        ab.create_experiment("exp1", [ABVariant("A", "m_a", 1.0)])
        # Not started yet
        v = ab.select_variant("NVDA", "exp1")
        assert v is None
