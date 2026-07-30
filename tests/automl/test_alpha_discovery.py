"""测试 Alpha Discovery & Factor Combiner。

覆盖: 因子模板注册、算子组合、候选生成、评分排序、
因子合并方法、组合因子评估。
"""

import numpy as np
import pytest

from services.automl.alpha_discovery import (
    AlphaCandidate,
    AlphaDiscovery,
    FactorTemplate,
    Operator,
)
from services.automl.factor_combiner import (
    CombineMethod,
    CombinedFactor,
    FactorCombiner,
)


# =================================================================
# Alpha Discovery
# =================================================================


class TestFactorTemplate:
    def test_create(self):
        ft = FactorTemplate(name="rsi_14", category="momentum", transform="identity")
        assert ft.name == "rsi_14"
        assert ft.category == "momentum"
        assert ft.transform == "identity"
        assert ft.params == {}

    def test_with_params(self):
        ft = FactorTemplate(
            name="sma",
            category="trend",
            params={"window": 20},
            tags=["moving_average"],
        )
        assert ft.params == {"window": 20}
        assert "moving_average" in ft.tags


class TestAlphaDiscoveryTemplateManagement:
    def test_register_single(self):
        ad = AlphaDiscovery()
        ft = FactorTemplate(name="rsi")
        ad.register_template(ft)
        assert ad.get_template("rsi").name == "rsi"

    def test_register_batch(self):
        ad = AlphaDiscovery()
        templates = [
            FactorTemplate(name="rsi", category="momentum"),
            FactorTemplate(name="sma_20", category="trend"),
            FactorTemplate(name="atr", category="volatility"),
        ]
        ad.register_templates(templates)
        assert len(ad.list_templates()) == 3

    def test_get_not_found(self):
        ad = AlphaDiscovery()
        with pytest.raises(KeyError):
            ad.get_template("nonexistent")

    def test_list_by_category(self):
        ad = AlphaDiscovery()
        ad.register_templates([
            FactorTemplate("rsi", category="momentum"),
            FactorTemplate("macd", category="momentum"),
            FactorTemplate("atr", category="volatility"),
        ])
        mom = ad.list_templates(category="momentum")
        assert len(mom) == 2
        vol = ad.list_templates(category="volatility")
        assert len(vol) == 1
        none = ad.list_templates(category="fundamental")
        assert none == []


class TestAlphaDiscoveryOperators:
    def setup_data(self):
        rng = np.random.RandomState(42)
        n = 100
        return {
            "factor_a": rng.randn(n).tolist(),
            "factor_b": rng.randn(n).tolist(),
            "factor_c": rng.randn(n).tolist(),
        }

    def test_add(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.ADD)
        assert result == [5.0, 7.0, 9.0]

    def test_sub(self):
        a = [7.0, 8.0, 9.0]
        b = [3.0, 4.0, 5.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.SUB)
        assert result == [4.0, 4.0, 4.0]

    def test_mul(self):
        a = [2.0, 3.0, 4.0]
        b = [3.0, 4.0, 5.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.MUL)
        assert result == [6.0, 12.0, 20.0]

    def test_div(self):
        a = [6.0, 8.0, 9.0]
        b = [2.0, 4.0, 3.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.DIV)
        assert result == [3.0, 2.0, 3.0]

    def test_div_by_zero(self):
        a = [1.0, 2.0]
        b = [0.0, 4.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.DIV)
        assert np.isnan(result[0])
        assert result[1] == 0.5

    def test_rank_add(self):
        a = [1.0, 2.0, 3.0]
        b = [3.0, 2.0, 1.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.RANK_ADD)
        assert len(result) == 3
        assert all(0 <= v <= 2 for v in result)

    def test_rank_mul(self):
        a = [1.0, 2.0, 3.0]
        b = [3.0, 2.0, 1.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.RANK_MUL)
        assert len(result) == 3
        assert all(0 <= v <= 1 for v in result)

    def test_zscore_add(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.ZSCORE_ADD)
        assert len(result) == 5

    def test_combine_rank_mul_triple(self):
        a = [1.0, 2.0, 3.0]
        b = [3.0, 2.0, 1.0]
        c = [1.0, 1.0, 1.0]
        result = AlphaDiscovery._combine_rank_mul(a, b, c)
        assert len(result) == 3
        assert all(0 <= v <= 1 for v in result)

    def test_apply_op_empty(self):
        result = AlphaDiscovery._apply_op([], [], Operator.ADD)
        assert result is None

    def test_apply_op_nan_handling(self):
        a = [1.0, np.nan, 3.0]
        b = [4.0, 5.0, 6.0]
        result = AlphaDiscovery._apply_op(a, b, Operator.ADD)
        assert len(result) == 3


class TestAlphaDiscoveryRun:
    @pytest.fixture
    def discovery(self):
        ad = AlphaDiscovery(seed=42)
        ad.register_templates([
            FactorTemplate("f1", category="price"),
            FactorTemplate("f2", category="momentum"),
            FactorTemplate("f3", category="volume"),
        ])
        return ad

    @pytest.fixture
    def data(self):
        rng = np.random.RandomState(42)
        n = 100
        return {
            "f1": (rng.randn(n) * 0.02 + 0.001).tolist(),
            "f2": (rng.randn(n) * 0.03).tolist(),
            "f3": (rng.randn(n) * 0.01 + 0.002).tolist(),
        }

    def test_discover_generates_candidates(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        candidates = discovery.discover(data, eval_fn, n_candidates=50, max_depth=2)
        assert len(candidates) > 0
        assert isinstance(candidates[0], AlphaCandidate)

    def test_candidates_sorted_by_score(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        candidates = discovery.discover(data, eval_fn, n_candidates=50)
        for i in range(len(candidates) - 1):
            assert candidates[i].score >= candidates[i + 1].score

    def test_top_candidates(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        discovery.discover(data, eval_fn, n_candidates=50)
        top5 = discovery.top_candidates(5)
        assert len(top5) <= 5

    def test_discover_empty_data(self, discovery):
        """Single factor shouldn't break discovery."""
        def eval_fn(name, values):
            return {"sharpe": 0, "composite": 0}
        candidates = discovery.discover(
            {"f1": [1.0, 2.0]}, eval_fn, n_candidates=10
        )
        assert isinstance(candidates, list)

    def test_candidate_count_and_best_score(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        discovery.discover(data, eval_fn, n_candidates=30)
        assert discovery.candidate_count() > 0
        assert discovery.candidate_count() <= 30
        assert isinstance(discovery.best_score(), float)

    def test_depth3_generates_triple_combos(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        candidates = discovery.discover(data, eval_fn, n_candidates=100, max_depth=3)
        # Check that at least one candidate uses depth-3 pattern
        triple_candidates = [c for c in candidates if len(c.factors) >= 3]
        assert len(triple_candidates) > 0
        assert any(op == Operator.RANK_MUL for c in triple_candidates for op in c.operators)

    def test_alpha_candidate_expression(self, discovery, data):
        def eval_fn(name, values):
            arr = np.array(values)
            arr = arr[~np.isnan(arr)]
            if len(arr) < 2:
                return {"sharpe": 0, "composite": 0}
            sharpe = float(np.mean(arr) / (np.std(arr) or 1))
            return {"sharpe": sharpe, "composite": sharpe}

        candidates = discovery.discover(data, eval_fn, n_candidates=20, max_depth=2)
        for c in candidates:
            assert c.name.startswith("alpha_")
            assert len(c.factors) > 0
            assert c.expression != ""


# =================================================================
# Factor Combiner
# =================================================================


class TestFactorCombiner:
    @pytest.fixture
    def factors(self):
        rng = np.random.RandomState(42)
        n = 200
        return {
            "f1": rng.randn(n).tolist(),
            "f2": rng.randn(n).tolist(),
            "f3": rng.randn(n).tolist(),
        }

    @pytest.fixture
    def combiner(self):
        return FactorCombiner()

    def test_equal_weight(self, combiner, factors):
        result = combiner.combine(factors, method=CombineMethod.EQUAL_WEIGHT)
        assert result.name != ""
        assert result.method == CombineMethod.EQUAL_WEIGHT
        assert len(result.weights) == 3

    def test_ic_weighted(self, combiner, factors):
        rng = np.random.RandomState(42)
        n = 200
        forward = rng.randn(n).tolist()
        result = combiner.combine(factors, targets=forward, method=CombineMethod.IC_WEIGHTED)
        assert result.method == CombineMethod.IC_WEIGHTED
        assert len(result.weights) == 3

    def test_regression(self, combiner, factors):
        rng = np.random.RandomState(42)
        n = 200
        forward = rng.randn(n).tolist()
        result = combiner.combine(factors, targets=forward, method=CombineMethod.REGRESSION)
        assert result.method == CombineMethod.REGRESSION
        assert len(result.weights) == 3

    def test_pca(self, combiner, factors):
        result = combiner.combine(factors, method=CombineMethod.PCA)
        assert result.method == CombineMethod.PCA
        assert len(result.weights) == 3

    def test_max_ic(self, combiner, factors):
        rng = np.random.RandomState(42)
        n = 200
        forward = rng.randn(n).tolist()
        result = combiner.combine(factors, targets=forward, method=CombineMethod.MAX_IC)
        assert result.method == CombineMethod.MAX_IC
        # MAX_IC picks only the best factor
        assert len(result.weights) >= 1
        assert sum(1 for w in result.weights.values() if w > 0) == 1

    def test_combined_values_length(self, combiner, factors):
        result = combiner.combine(factors)
        assert len(result.values) == 200

    def test_default_method(self, combiner, factors):
        result = combiner.combine(factors)
        assert result.method == CombineMethod.EQUAL_WEIGHT

    def test_single_factor(self, combiner):
        result = combiner.combine({"f1": [1.0, 2.0, 3.0]})
        assert result.weights == {"f1": 1.0}
        assert result.values == [1.0, 2.0, 3.0]

    def test_empty_factors(self, combiner):
        result = combiner.combine({})
        assert result.values == []
        assert result.weights == {}

    def test_factors_mismatched_lengths(self, combiner):
        """Factors with different lengths should be trimmed."""
        factors = {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [10.0, 20.0, 30.0],
        }
        result = combiner.combine(factors)
        assert len(result.values) == 3  # min length

    def test_metric_computation(self, combiner, factors):
        result = combiner.combine(factors, method=CombineMethod.EQUAL_WEIGHT)
        assert "sharpe" in result.metrics or result.metrics == {}

    def test_all_methods_work(self, combiner, factors):
        rng = np.random.RandomState(42)
        n = 200
        forward = rng.randn(n).tolist()
        for method in CombineMethod:
            # Methods that need targets
            if method in (CombineMethod.IC_WEIGHTED, CombineMethod.REGRESSION, CombineMethod.MAX_IC):
                result = combiner.combine(factors, targets=forward, method=method)
            else:
                result = combiner.combine(factors, method=method)
            assert result.method == method
            assert len(result.values) > 0

    def test_regression_with_few_factors(self, combiner):
        rng = np.random.RandomState(42)
        n = 100
        factors = {"f1": rng.randn(n).tolist(), "f2": rng.randn(n).tolist()}
        forward = rng.randn(n).tolist()
        result = combiner.combine(factors, targets=forward, method=CombineMethod.REGRESSION)
        assert len(result.weights) == 2
