"""测试 AutoML Optimizer — 搜索空间与超参数优化。

覆盖: SearchSpace 定义、Random/Grid/Bayesian/TPE 策略、
ModelConfig、参数采样和批量配置生成。
"""

import pytest
import numpy as np

from services.automl.search_space import (
    CategoricalParam,
    ContinuousParam,
    DiscreteParam,
    ModelConfig,
    ParamType,
    SearchSpace,
)
from services.automl.optimizer import (
    HyperOptimizer,
    OptimizationResult,
    SearchStrategy,
)


# =================================================================
# SearchSpace & Params
# =================================================================


class TestCategoricalParam:
    def test_create(self):
        p = CategoricalParam("boosting_type", choices=["gbdt", "dart", "goss"], default="gbdt")
        assert p.name == "boosting_type"
        assert p.choices == ["gbdt", "dart", "goss"]
        assert p.default == "gbdt"

    def test_sample_in_choices(self):
        p = CategoricalParam("algo", choices=["a", "b", "c"])
        for _ in range(50):
            assert p.sample() in ["a", "b", "c"]

    def test_sample_deterministic(self):
        p = CategoricalParam("x", choices=[1, 2, 3])
        rng = np.random.RandomState(42)
        results = [p.sample(rng) for _ in range(20)]
        assert all(v in [1, 2, 3] for v in results)


class TestContinuousParam:
    def test_create(self):
        p = ContinuousParam("lr", low=0.001, high=0.1, log_scale=True, default=0.01)
        assert p.name == "lr"
        assert p.low == 0.001
        assert p.high == 0.1
        assert p.log_scale is True
        assert p.default == 0.01

    def test_sample_range(self):
        p = ContinuousParam("lr", 0.0, 1.0)
        rng = np.random.RandomState(42)
        for _ in range(50):
            v = p.sample(rng)
            assert 0.0 <= v <= 1.0

    def test_log_scale_sample(self):
        p = ContinuousParam("lr", 0.01, 1.0, log_scale=True)
        rng = np.random.RandomState(42)
        for _ in range(50):
            v = p.sample(rng)
            assert 0.01 <= v <= 1.0


class TestDiscreteParam:
    def test_create(self):
        p = DiscreteParam("depth", low=3, high=12, step=3, default=6)
        assert p.name == "depth"
        assert p.low == 3
        assert p.high == 12
        assert p.step == 3
        assert p.default == 6

    def test_values(self):
        p = DiscreteParam("n", 0, 10, step=2)
        assert p.values == [0, 2, 4, 6, 8, 10]

    def test_sample_in_range(self):
        p = DiscreteParam("n", 0, 10, step=2)
        rng = np.random.RandomState(42)
        for _ in range(20):
            v = p.sample(rng)
            assert v in p.values


class TestModelConfig:
    def test_create(self):
        mc = ModelConfig(name="lightgbm", module="lightgbm", tags=["boosting"])
        assert mc.name == "lightgbm"
        assert mc.tags == ["boosting"]

    def test_sample_params(self):
        p1 = DiscreteParam("num_leaves", 8, 64, step=8)
        p2 = ContinuousParam("lr", 0.01, 0.1, log_scale=True)
        mc = ModelConfig(name="lgb", params=[p1, p2])
        rng = np.random.RandomState(42)
        params = mc.sample_params(rng)
        assert "num_leaves" in params
        assert "lr" in params
        assert isinstance(params["num_leaves"], int)
        assert isinstance(params["lr"], float)


class TestSearchSpace:
    def test_create_default(self):
        ss = SearchSpace()
        assert ss.name == "default"
        assert ss.max_trials == 100

    def test_add_feature_group(self):
        ss = SearchSpace()
        ss.add_feature_group("momentum", ["rsi_14", "macd"])
        assert "momentum" in ss.feature_groups
        assert "rsi_14" in ss.feature_universe
        assert "macd" in ss.feature_universe

    def test_add_model(self):
        ss = SearchSpace()
        mc = ss.add_model("lightgbm", module="lightgbm")
        assert mc.name == "lightgbm"
        assert len(ss.model_candidates) == 1

    def test_sample_config(self):
        ss = SearchSpace()
        p = CategoricalParam("boosting", choices=["gbdt", "dart"])
        ss.add_model("lgb", params=[p])
        rng = np.random.RandomState(42)
        config = ss.sample_config(rng)
        assert config["model"] == "lgb"
        assert "params" in config
        assert "boosting" in config["params"]

    def test_grid_configs(self):
        ss = SearchSpace()
        p1 = CategoricalParam("boosting", choices=["gbdt", "dart"])
        p2 = DiscreteParam("depth", 3, 5, step=1)
        ss.add_model("lgb", params=[p1, p2])
        configs = ss.grid_configs()
        assert len(configs) == 2 * 3  # 2 categorical * 3 discrete
        for c in configs:
            assert c["model"] == "lgb"
            assert c["params"]["boosting"] in ["gbdt", "dart"]
            assert c["params"]["depth"] in [3, 4, 5]

    def test_grid_configs_multiple_models(self):
        ss = SearchSpace()
        ss.add_model("lgb", params=[CategoricalParam("b", choices=["a"])])
        ss.add_model("xgb", params=[CategoricalParam("b", choices=["a"])])
        configs = ss.grid_configs()
        assert len(configs) == 2

    def test_summary(self):
        ss = SearchSpace(name="test")
        ss.add_feature_group("price", ["close", "volume"])
        ss.add_model("lgb")
        s = ss.summary()
        assert s["name"] == "test"
        assert s["features"] == 2
        assert s["model_candidates"] == ["lgb"]


# =================================================================
# Optimizer
# =================================================================


def _simple_objective(config):
    """Simple quadratic objective: -(x-3)^2 -> max at x=3."""
    val = config.get("params", {}).get("x", 0)
    score = -(val - 3) ** 2 + 10
    return score


class TestHyperOptimizer:
    @pytest.fixture
    def search_space(self):
        ss = SearchSpace(name="test", max_trials=30, timeout_seconds=60)
        ss.add_model("dummy", params=[
            ContinuousParam("x", 0.0, 6.0),
        ])
        return ss

    def test_random_search(self, search_space):
        opt = HyperOptimizer(search_space, strategy=SearchStrategy.RANDOM, seed=42)
        result = opt.optimize(_simple_objective, n_trials=30, maximize=True)
        assert result.total_trials > 0
        assert result.best_score >= 9.0  # should be near 10
        assert 2.0 <= result.best_config["params"]["x"] <= 4.0
        assert result.strategy == SearchStrategy.RANDOM
        assert result.elapsed_seconds > 0

    def test_grid_search(self):
        ss = SearchSpace(name="grid_test")
        p1 = DiscreteParam("n1", 1, 3, step=1)
        p2 = DiscreteParam("n2", 5, 7, step=2)
        ss.add_model("dummy", params=[p1, p2])
        opt = HyperOptimizer(ss, strategy=SearchStrategy.GRID)
        result = opt.optimize(
            lambda c: c["params"]["n1"] + c["params"]["n2"],
            maximize=True,
        )
        assert result.total_trials == 3 * 2  # all combos
        # Best: n1=3, n2=7 => 10
        assert result.best_score == 10

    def test_bayesian_search(self, search_space):
        opt = HyperOptimizer(search_space, strategy=SearchStrategy.BAYESIAN, seed=42)
        result = opt.optimize(_simple_objective, n_trials=20, maximize=True)
        assert result.total_trials > 0
        assert result.strategy == SearchStrategy.BAYESIAN

    def test_tpe_search(self, search_space):
        opt = HyperOptimizer(search_space, strategy=SearchStrategy.TPE, seed=42)
        result = opt.optimize(_simple_objective, n_trials=30, maximize=True)
        assert result.total_trials > 0
        assert result.best_score >= 9.0
        assert result.strategy == SearchStrategy.TPE

    def test_default_strategy_is_random(self, search_space):
        opt = HyperOptimizer(search_space)
        assert opt.strategy == SearchStrategy.RANDOM

    def test_optimize_minimize(self, search_space):
        opt = HyperOptimizer(search_space, seed=42)
        result = opt.optimize(_simple_objective, n_trials=30, maximize=False)
        assert result.total_trials > 0
        # Worst (best for minimize) should be at x=0 or x=6
        # Score at x=0: 1, at x=3: 10 -> minimize should pick 1
        assert result.best_score <= 5  # far from optimum

    def test_random_search_result_fields(self, search_space):
        opt = HyperOptimizer(search_space, seed=42)
        result = opt.optimize(_simple_objective, n_trials=5, maximize=True)
        assert isinstance(result, OptimizationResult)
        assert isinstance(result.best_config, dict)
        assert isinstance(result.best_score, float)
        assert len(result.all_results) > 0

    def test_grid_search_result_fields(self):
        ss = SearchSpace()
        ss.add_model("m", params=[CategoricalParam("x", choices=["a", "b"])])
        opt = HyperOptimizer(ss, strategy=SearchStrategy.GRID)
        result = opt.optimize(lambda c: {"a": 1, "b": 2}[c["params"]["x"]], maximize=True)
        assert result.total_trials == 2
        assert result.best_score == 2

    def test_timeout(self, search_space):
        opt = HyperOptimizer(search_space, seed=42)
        result = opt.optimize(_simple_objective, n_trials=1000, timeout_seconds=1, maximize=True)
        assert result.total_trials > 0
        assert result.elapsed_seconds < 5  # should respect timeout roughly

    def test_unknown_strategy_raises(self, search_space):
        opt = HyperOptimizer(search_space)
        opt.strategy = "invalid"  # type: ignore
        with pytest.raises(ValueError, match="Unknown strategy"):
            opt.optimize(_simple_objective, n_trials=5)
