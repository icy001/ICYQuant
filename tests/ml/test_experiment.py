"""Tests for ML Experiment Tracking."""

from services.ml.experiment import (
    ExperimentTracker,
    Experiment,
    ExperimentStatus,
    RunInfo,
)


class TestRunInfo:
    """Tests for RunInfo dataclass."""

    def test_create_run(self):
        """创建运行记录应正确设置字段。"""
        run = RunInfo()
        assert run.run_id != ""
        assert run.status == ExperimentStatus.CREATED
        assert run.params == {}
        assert run.metrics == {}

    def test_add_metric(self):
        """添加指标应正确存储。"""
        run = RunInfo()
        run.add_metric("sharpe", 2.03)
        run.add_metric("accuracy", 0.742)
        assert run.metrics["sharpe"] == 2.03
        assert run.metrics["accuracy"] == 0.742

    def test_add_param(self):
        """添加参数应正确存储。"""
        run = RunInfo()
        run.add_param("learning_rate", 0.05)
        run.add_param("max_depth", 6)
        assert run.params["learning_rate"] == 0.05
        assert run.params["max_depth"] == 6

    def test_to_dict(self):
        """to_dict 应正确序列化。"""
        run = RunInfo(git_commit="abc123")
        run.add_metric("sharpe", 2.0)
        run.add_param("lr", 0.01)
        d = run.to_dict()
        assert d["git_commit"] == "abc123"
        assert d["metrics"]["sharpe"] == 2.0
        assert d["params"]["lr"] == 0.01


class TestExperiment:
    """Tests for Experiment dataclass."""

    def test_create_experiment(self):
        """创建实验应设置所有字段。"""
        exp = Experiment(
            name="alpha_v18",
            framework="LightGBM",
            dataset="US_STOCK_2025",
            features=128,
        )
        assert exp.name == "alpha_v18"
        assert exp.framework == "LightGBM"
        assert exp.dataset == "US_STOCK_2025"
        assert exp.features == 128
        assert exp.status == ExperimentStatus.CREATED
        assert exp.id != ""

    def test_get_latest_run_empty(self):
        """没有运行时应返回 None。"""
        exp = Experiment(name="test")
        assert exp.get_latest_run() is None

    def test_get_latest_run(self):
        """应返回最后一个运行。"""
        exp = Experiment(name="test")
        exp.runs = [
            RunInfo(run_id="run_1"),
            RunInfo(run_id="run_2"),
            RunInfo(run_id="run_3"),
        ]
        latest = exp.get_latest_run()
        assert latest is not None
        assert latest.run_id == "run_3"

    def test_get_best_run_maximize(self):
        """应返回指定指标值最高的运行。"""
        exp = Experiment(name="test")
        r1 = RunInfo(run_id="r1")
        r1.add_metric("sharpe", 1.5)
        r2 = RunInfo(run_id="r2")
        r2.add_metric("sharpe", 2.5)
        r3 = RunInfo(run_id="r3")
        r3.add_metric("sharpe", 2.0)
        exp.runs = [r1, r2, r3]
        best = exp.get_best_run("sharpe", maximize=True)
        assert best is not None
        assert best.run_id == "r2"
        assert best.metrics["sharpe"] == 2.5

    def test_get_best_run_minimize(self):
        """应返回指定指标值最低的运行。"""
        exp = Experiment(name="test")
        r1 = RunInfo(run_id="r1")
        r1.add_metric("loss", 0.5)
        r2 = RunInfo(run_id="r2")
        r2.add_metric("loss", 0.3)
        r3 = RunInfo(run_id="r3")
        r3.add_metric("loss", 0.7)
        exp.runs = [r1, r2, r3]
        best = exp.get_best_run("loss", maximize=False)
        assert best is not None
        assert best.run_id == "r2"

    def test_get_best_run_empty(self):
        """没有运行时 get_best_run 应返回 None。"""
        exp = Experiment(name="test")
        assert exp.get_best_run("sharpe") is None


class TestExperimentTracker:
    """Tests for ExperimentTracker."""

    def test_create_experiment(self):
        """创建实验应返回 Experiment 对象。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("alpha_v18", "LightGBM")
        assert exp.name == "alpha_v18"
        assert exp.framework == "LightGBM"

    def test_get_experiment(self):
        """通过 ID 获取实验应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test", "LightGBM")
        found = tracker.get_experiment(exp.id)
        assert found is not None
        assert found.name == "test"

    def test_get_nonexistent(self):
        """获取不存在的实验应返回 None。"""
        tracker = ExperimentTracker()
        assert tracker.get_experiment("fake_id") is None

    def test_list_experiments(self):
        """列出实验应按时间倒序排列。"""
        tracker = ExperimentTracker()
        tracker.create_experiment("exp_1")
        tracker.create_experiment("exp_2")
        tracker.create_experiment("exp_3")
        exps = tracker.list_experiments()
        assert len(exps) == 3
        # Latest first
        assert exps[0].name == "exp_3"

    def test_list_by_status(self):
        """按状态过滤实验应正确。"""
        tracker = ExperimentTracker()
        e1 = tracker.create_experiment("e1")
        e2 = tracker.create_experiment("e2")
        tracker.update_experiment_status(e2.id, ExperimentStatus.COMPLETED)
        active = tracker.list_experiments(status=ExperimentStatus.CREATED)
        assert len(active) == 1
        assert active[0].name == "e1"

    def test_delete_experiment(self):
        """删除实验应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("delete_me")
        assert tracker.count() == 1
        assert tracker.delete_experiment(exp.id)
        assert tracker.count() == 0

    def test_delete_nonexistent(self):
        """删除不存在的实验应返回 False。"""
        tracker = ExperimentTracker()
        assert tracker.delete_experiment("fake") is False

    def test_start_run(self):
        """启动运行应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        assert run is not None
        assert run.status == ExperimentStatus.RUNNING
        assert len(exp.runs) == 1

    def test_start_run_nonexistent(self):
        """在不存在的实验中启动运行应返回 None。"""
        tracker = ExperimentTracker()
        assert tracker.start_run("fake_id") is None

    def test_finish_run(self):
        """结束运行应正确更新状态。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        assert tracker.finish_run(exp.id, run.run_id)
        assert run.status == ExperimentStatus.COMPLETED
        assert run.finished_at is not None

    def test_finish_nonexistent(self):
        """结束不存在的运行应返回 False。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        assert tracker.finish_run(exp.id, "bad_run_id") is False

    def test_log_params(self):
        """记录参数应正确保存。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        tracker.log_params(exp.id, run.run_id, {"lr": 0.05, "depth": 6})
        assert run.params["lr"] == 0.05
        assert run.params["depth"] == 6

    def test_log_metrics(self):
        """记录指标应正确保存。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        tracker.log_metrics(exp.id, run.run_id, {"sharpe": 2.03, "accuracy": 0.742})
        assert run.metrics["sharpe"] == 2.03
        assert run.metrics["accuracy"] == 0.742

    def test_log_param_single(self):
        """记录单个参数应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        assert tracker.log_param(exp.id, run.run_id, "lr", 0.01)
        assert run.params["lr"] == 0.01

    def test_log_metric_single(self):
        """记录单个指标应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        assert tracker.log_metric(exp.id, run.run_id, "sharpe", 2.5)
        assert run.metrics["sharpe"] == 2.5

    def test_log_to_bad_run(self):
        """向不存在的运行记录应返回 False。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        assert tracker.log_metric(exp.id, "bad_run", "sharpe", 1.0) is False
        assert tracker.log_param(exp.id, "bad_run", "lr", 0.01) is False

    def test_log_common_params(self):
        """记录共享参数应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        tracker.log_common_params(exp.id, {"seed": 42, "cross_val": 5})
        assert exp.common_params["seed"] == 42

    def test_set_tags(self):
        """设置标签应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        tracker.set_tags(exp.id, {"env": "dev", "team": "alpha"})
        assert exp.tags["env"] == "dev"

    def test_search_by_name(self):
        """按名称搜索应正确。"""
        tracker = ExperimentTracker()
        tracker.create_experiment("alpha_v17")
        tracker.create_experiment("alpha_v18")
        tracker.create_experiment("beta_v01")
        results = tracker.search(name_contains="alpha")
        assert len(results) == 2

    def test_search_by_framework(self):
        """按框架搜索应正确。"""
        tracker = ExperimentTracker()
        tracker.create_experiment("lgb_exp", framework="LightGBM")
        tracker.create_experiment("xgb_exp", framework="XGBoost")
        results = tracker.search(framework="LightGBM")
        assert len(results) == 1
        assert results[0].name == "lgb_exp"

    def test_search_by_tags(self):
        """按标签搜索应正确。"""
        tracker = ExperimentTracker()
        e1 = tracker.create_experiment("e1")
        e2 = tracker.create_experiment("e2")
        tracker.set_tags(e1.id, {"type": "alpha"})
        tracker.set_tags(e2.id, {"type": "risk"})
        results = tracker.search(tags={"type": "alpha"})
        assert len(results) == 1
        assert results[0].name == "e1"

    def test_compare_experiments(self):
        """实验对比应返回各实验的最新指标。"""
        tracker = ExperimentTracker()
        e1 = tracker.create_experiment("exp_a", framework="LightGBM")
        r1 = tracker.start_run(e1.id)
        tracker.log_metrics(e1.id, r1.run_id, {"sharpe": 2.0, "accuracy": 0.8})
        tracker.finish_run(e1.id, r1.run_id)

        e2 = tracker.create_experiment("exp_b", framework="XGBoost")
        r2 = tracker.start_run(e2.id)
        tracker.log_metrics(e2.id, r2.run_id, {"sharpe": 1.5, "accuracy": 0.75})
        tracker.finish_run(e2.id, r2.run_id)

        comparison = tracker.compare_experiments([e1.id, e2.id])
        assert "exp_a" in comparison
        assert "exp_b" in comparison
        assert comparison["exp_a"]["latest_metrics"]["sharpe"] == 2.0

    def test_count_and_run_count(self):
        """count 和 run_count 应正确。"""
        tracker = ExperimentTracker()
        e1 = tracker.create_experiment("e1")
        e2 = tracker.create_experiment("e2")
        tracker.start_run(e1.id)
        tracker.start_run(e1.id)
        tracker.start_run(e2.id)
        assert tracker.count() == 2
        assert tracker.run_count() == 3

    def test_multiple_runs_metrics(self):
        """多次运行应分别记录指标。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        r1 = tracker.start_run(exp.id)
        tracker.log_metrics(exp.id, r1.run_id, {"sharpe": 1.0})
        tracker.finish_run(exp.id, r1.run_id)

        r2 = tracker.start_run(exp.id)
        tracker.log_metrics(exp.id, r2.run_id, {"sharpe": 2.0})
        tracker.finish_run(exp.id, r2.run_id)

        assert len(exp.runs) == 2
        assert exp.runs[0].metrics["sharpe"] == 1.0
        assert exp.runs[1].metrics["sharpe"] == 2.0

    def test_experiment_with_tags_and_description(self):
        """创建带描述和标签的实验应正确。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment(
            "alpha_v18",
            framework="LightGBM",
            description="Alpha factor model v18",
            tags={"type": "alpha", "market": "US"},
            dataset="US_STOCK_2025",
            features=128,
        )
        assert exp.description == "Alpha factor model v18"
        assert exp.tags["type"] == "alpha"
        assert exp.dataset == "US_STOCK_2025"
        assert exp.features == 128

    def test_finish_run_with_failed_status(self):
        """以失败状态结束运行。"""
        tracker = ExperimentTracker()
        exp = tracker.create_experiment("test")
        run = tracker.start_run(exp.id)
        tracker.finish_run(exp.id, run.run_id, ExperimentStatus.FAILED)
        assert run.status == ExperimentStatus.FAILED
