"""测试 Feature Pipeline — 特征流水线全链路。

覆盖: PipelineConfig, FeaturePipeline 执行, PipelineResult, Orchestrator,
Cache, Scheduler, Validator。
"""

import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from services.feature_engineering.pipeline import (
    FeaturePipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
    PipelineStatus,
)
from services.feature_engineering.orchestrator import (
    Checkpoint,
    OrchestratorConfig,
    PipelineOrchestrator,
    RetryPolicy,
    RunStatus,
)
from services.feature_engineering.cache import (
    CachePolicy,
    FeatureCache,
)
from services.feature_engineering.scheduler import (
    PipelineScheduler,
    ScheduleConfig,
    TriggerType,
)
from services.feature_engineering.validator import (
    PipelineValidationRule,
    PipelineValidator,
)


# ============================================================
# Pipeline Config
# ============================================================

class TestPipelineConfig:
    def test_default_config(self):
        cfg = PipelineConfig()
        assert cfg.name == "default"
        assert cfg.source == "market_data"
        assert cfg.transforms == []
        assert cfg.validate is True
        assert cfg.cache_enabled is True

    def test_custom_config(self):
        cfg = PipelineConfig(
            name="alpha_daily",
            transforms=["return", "ema20"],
            tags=["alpha"],
            max_retries=5,
        )
        assert cfg.name == "alpha_daily"
        assert cfg.transforms == ["return", "ema20"]
        assert cfg.tags == ["alpha"]
        assert cfg.max_retries == 5


# ============================================================
# FeaturePipeline
# ============================================================

class TestFeaturePipelineBasic:
    @pytest.fixture
    def pipeline(self):
        return FeaturePipeline(PipelineConfig(
            name="test_pipeline",
            transforms=["test_transform"],
            validate=True,
        ))

    @pytest.fixture
    def raw_data(self):
        return {
            "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "volume": [1000.0, 1100.0, 1050.0, 1200.0, 1150.0],
        }

    def test_pipeline_creation(self, pipeline):
        assert pipeline.name == "test_pipeline"
        assert pipeline.status == PipelineStatus.IDLE

    def test_register_transform(self, pipeline):
        def dummy_transform(data):
            return {"ema": [v * 1.1 for v in data.get("close", [])]}

        pipeline.register_transform("test_transform", dummy_transform)
        assert "test_transform" in pipeline._transforms_registry

    def test_pipeline_run(self, pipeline, raw_data):
        def dummy_transform(data):
            return {"ema": [v * 1.1 for v in data.get("close", [])]}

        pipeline.register_transform("test_transform", dummy_transform)
        result = pipeline.run(raw_data)

        assert result.status == PipelineStatus.COMPLETED
        assert result.feature_count > 0
        assert "close" in result.feature_names or "ema" in result.feature_names

    def test_pipeline_to_dict(self, pipeline):
        d = pipeline.to_dict()
        assert d["name"] == "test_pipeline"
        assert d["transforms"] == ["test_transform"]

    def test_pipeline_reset(self, pipeline):
        pipeline.status = PipelineStatus.COMPLETED
        pipeline.reset()
        assert pipeline.status == PipelineStatus.IDLE


class TestFeaturePipelineStages:
    @pytest.fixture
    def raw_data(self):
        return {"close": [100.0, 101.0, 102.0, 103.0, 104.0]}

    def test_stages_completed(self, raw_data):
        def t1(data):
            return {"ret": [0.0, 0.01, 0.0099, 0.0098, 0.0097]}

        pipeline = FeaturePipeline(PipelineConfig(
            name="stage_test",
            transforms=["t1"],
            validate=True,
        ))
        pipeline.register_transform("t1", t1)
        result = pipeline.run(raw_data)

        stages = [s.value for s in result.stages_completed]
        assert "load" in stages
        assert "transform" in stages
        assert "publish" in stages
        assert "done" in stages

    def test_unknown_transform_warns(self, raw_data):
        pipeline = FeaturePipeline(PipelineConfig(
            name="warn_test",
            transforms=["nonexistent"],
        ))
        result = pipeline.run(raw_data)
        assert any("not registered" in w for w in result.warnings)

    def test_elapsed_time(self, raw_data):
        pipeline = FeaturePipeline(PipelineConfig(name="time_test"))
        result = pipeline.run(raw_data)
        assert result.elapsed_seconds >= 0

    def test_clean_all_nan_column(self):
        pipeline = FeaturePipeline(PipelineConfig(name="clean_test"))
        result = pipeline.run({"bad_col": [float("nan"), float("nan")]})
        assert "bad_col" not in result.feature_names
        assert any("all-NaN" in w for w in result.warnings)


# ============================================================
# Pipeline Orchestrator
# ============================================================

class TestPipelineOrchestrator:
    @pytest.fixture
    def orch(self):
        return PipelineOrchestrator()

    @pytest.fixture
    def pipeline(self):
        return FeaturePipeline(PipelineConfig(name="test_orch"))

    @pytest.fixture
    def raw_data(self):
        return {"close": [100.0, 101.0, 102.0]}

    def test_register_pipeline(self, orch, pipeline):
        orch.register(pipeline)
        assert "test_orch" in orch.list_pipelines()

    def test_unregister_pipeline(self, orch, pipeline):
        orch.register(pipeline)
        orch.unregister("test_orch")
        assert "test_orch" not in orch.list_pipelines()

    def test_run_pipeline(self, orch, pipeline, raw_data):
        orch.register(pipeline)
        result = orch.run("test_orch", raw_data)
        assert result.status == PipelineStatus.COMPLETED

    def test_run_unregistered_raises(self, orch, raw_data):
        with pytest.raises(KeyError, match="not registered"):
            orch.run("nonexistent", raw_data)

    def test_run_all(self, orch, raw_data):
        p1 = FeaturePipeline(PipelineConfig(name="p1"))
        p2 = FeaturePipeline(PipelineConfig(name="p2"))
        orch.register(p1)
        orch.register(p2)
        results = orch.run_all(raw_data)
        assert "p1" in results
        assert "p2" in results
        assert results["p1"].status == PipelineStatus.COMPLETED

    def test_get_status(self, orch, pipeline, raw_data):
        orch.register(pipeline)
        orch.run("test_orch", raw_data)
        status = orch.get_status("test_orch")
        assert status == RunStatus.SUCCESS

    def test_get_history(self, orch, pipeline, raw_data):
        orch.register(pipeline)
        orch.run("test_orch", raw_data)
        history = orch.get_history()
        assert "test_orch" in history

    def test_cancel_pipeline(self, orch, pipeline):
        orch.register(pipeline)
        # Pipeline not running, cancel should return False
        result = orch.cancel("test_orch")
        assert result is False

    def test_summary(self, orch, pipeline):
        orch.register(pipeline)
        s = orch.summary()
        assert s["total_pipelines"] == 1
        assert "test_orch" in s["registered"]


class TestOrchestratorConfig:
    def test_default_config(self):
        cfg = OrchestratorConfig()
        assert cfg.max_retries == 3
        assert cfg.retry_policy == RetryPolicy.EXPONENTIAL
        assert cfg.checkpoint_enabled is True

    def test_custom_config(self):
        cfg = OrchestratorConfig(max_retries=5, retry_policy=RetryPolicy.IMMEDIATE)
        assert cfg.max_retries == 5
        assert cfg.retry_policy == RetryPolicy.IMMEDIATE


class TestCheckpoint:
    def test_checkpoint_creation(self):
        cp = Checkpoint(
            run_id="abc123",
            pipeline_name="alpha",
            stage="transform",
            progress=60.0,
        )
        assert cp.run_id == "abc123"
        assert cp.stage == "transform"
        assert cp.progress == 60.0

    def test_checkpoint_auto_timestamp(self):
        cp = Checkpoint(run_id="x", pipeline_name="y", stage="done")
        assert cp.created_at > 0


# ============================================================
# Feature Cache
# ============================================================

class TestFeatureCache:
    @pytest.fixture
    def cache(self):
        return FeatureCache(policy=CachePolicy.ALWAYS, ttl=3600)

    def test_put_and_get(self, cache):
        cache.put("ema20", "2024-01-01", [1.0, 2.0, 3.0])
        result = cache.get("ema20", "2024-01-01")
        assert result == [1.0, 2.0, 3.0]

    def test_miss(self, cache):
        result = cache.get("nonexistent", "2024-01-01")
        assert result is None

    def test_has(self, cache):
        cache.put("ema20", "2024-01-01", [1.0, 2.0, 3.0])
        assert cache.has("ema20", "2024-01-01")
        assert not cache.has("ema20", "2024-01-02")

    def test_hit_rate(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        cache.get("ema20", "2024-01-01")  # hit
        cache.get("ema20", "2024-01-02")  # miss
        assert cache.hit_rate == 0.5

    def test_invalidate_all(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        cache.put("momentum", "2024-01-01", [2.0])
        count = cache.invalidate()
        assert count == 2
        assert cache.size == 0

    def test_invalidate_feature(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        cache.put("momentum", "2024-01-01", [2.0])
        cache.invalidate(feature_name="ema20")
        assert not cache.has("ema20", "2024-01-01")
        assert cache.has("momentum", "2024-01-01")

    def test_get_new_partitions(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        new = cache.get_new_partitions("ema20", ["2024-01-01", "2024-01-02", "2024-01-03"])
        assert new == ["2024-01-02", "2024-01-03"]

    def test_stats(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["policy"] == "always"
        assert "hit_rate" in stats

    def test_ttl_expiry(self):
        cache = FeatureCache(policy=CachePolicy.TTL, ttl=0.01)
        cache.put("ema20", "2024-01-01", [1.0])
        time.sleep(0.02)
        assert cache.get("ema20", "2024-01-01") is None

    def test_never_cache(self):
        cache = FeatureCache(policy=CachePolicy.NEVER)
        cache.put("ema20", "2024-01-01", [1.0])
        assert cache.get("ema20", "2024-01-01") is None

    def test_clear(self, cache):
        cache.put("ema20", "2024-01-01", [1.0])
        cache.clear()
        assert cache.size == 0
        assert cache.hit_rate == 0.0

    def test_eviction(self):
        cache = FeatureCache(max_entries=3, policy=CachePolicy.ALWAYS)
        for i in range(5):
            cache.put(f"feature_{i}", "2024-01-01", [float(i)])
        assert cache.size <= 3

    def test_version_check(self):
        cache = FeatureCache(policy=CachePolicy.VERSION, default_version="v1")
        cache.put("ema20", "2024-01-01", [1.0], version="v1")
        assert cache.has("ema20", "2024-01-01", version="v1")
        assert not cache.has("ema20", "2024-01-01", version="v2")


# ============================================================
# Pipeline Validator
# ============================================================

class TestPipelineValidator:
    @pytest.fixture
    def validator(self):
        return PipelineValidator(
            expected_columns=["close", "return"],
            min_rows=3,
        )

    def test_valid_data(self, validator):
        features = {
            "close": [100.0, 101.0, 102.0, 103.0],
            "return": [0.0, 0.01, 0.0099, 0.0098],
        }
        report = validator.validate(features)
        assert report.is_valid

    def test_missing_columns(self, validator):
        features = {"close": [100.0, 101.0]}
        report = validator.validate(features)
        assert not report.is_valid
        assert any("Missing" in e for e in report.errors)

    def test_all_nan_column(self):
        v = PipelineValidator(
            rules=[PipelineValidationRule.NO_ALL_NAN],
        )
        features = {"bad": [float("nan"), float("nan")]}
        report = v.validate(features)
        assert not report.is_valid

    def test_insufficient_rows(self, validator):
        features = {"close": [100.0, 101.0], "return": [0.0, 0.01]}
        report = validator.validate(features)
        assert not report.is_valid

    def test_row_count_inconsistency(self):
        v = PipelineValidator(
            rules=[PipelineValidationRule.ROW_COUNT_CONSISTENCY],
        )
        features = {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0]}
        report = v.validate(features)
        assert not report.is_valid

    def test_all_zero_warning(self):
        v = PipelineValidator(
            rules=[PipelineValidationRule.NO_ALL_ZERO],
        )
        features = {"zero_col": [0.0, 0.0, 0.0]}
        report = v.validate(features)
        # Warning, not hard failure
        assert any("All-zero" in w for w in report.warnings)

    def test_constant_warning(self):
        v = PipelineValidator(
            rules=[PipelineValidationRule.NO_CONSTANT],
        )
        features = {"const": [5.0, 5.0, 5.0]}
        report = v.validate(features)
        assert any("Constant" in w for w in report.warnings)


# ============================================================
# Pipeline Scheduler
# ============================================================

class TestPipelineScheduler:
    @pytest.fixture
    def scheduler(self):
        orch = PipelineOrchestrator()
        p = FeaturePipeline(PipelineConfig(name="scheduled_pipeline"))
        orch.register(p)
        return PipelineScheduler(orchestrator=orch)

    def test_schedule_pipeline(self, scheduler):
        entry = scheduler.schedule("scheduled_pipeline", trigger="interval:3600")
        assert entry.pipeline_name == "scheduled_pipeline"
        assert entry.config.trigger == TriggerType.INTERVAL
        assert entry.config.expression == "3600"

    def test_schedule_cron(self, scheduler):
        entry = scheduler.schedule("scheduled_pipeline", trigger="cron:0 3 * * *")
        assert entry.config.trigger == TriggerType.CRON
        assert entry.config.expression == "0 3 * * *"

    def test_schedule_manual(self, scheduler):
        entry = scheduler.schedule("scheduled_pipeline", trigger="manual")
        assert entry.config.trigger == TriggerType.MANUAL
        assert entry.next_run is None

    def test_list_schedules(self, scheduler):
        scheduler.schedule("scheduled_pipeline", trigger="interval:3600")
        schedules = scheduler.list_schedules()
        assert len(schedules) == 1

    def test_unschedule(self, scheduler):
        scheduler.schedule("scheduled_pipeline", trigger="interval:3600")
        assert scheduler.unschedule("scheduled_pipeline")
        assert not scheduler.unschedule("scheduled_pipeline")  # already removed

    def test_summary(self, scheduler):
        scheduler.schedule("scheduled_pipeline", trigger="interval:3600")
        s = scheduler.summary()
        assert s["total_schedules"] == 1

    def test_stop_not_running(self, scheduler):
        # Should not raise
        scheduler.stop()
        assert not scheduler.is_running

    def test_get_schedule(self, scheduler):
        scheduler.schedule("scheduled_pipeline", trigger="interval:3600")
        entry = scheduler.get_schedule("scheduled_pipeline")
        assert entry is not None
        assert entry.run_count == 0

    def test_cron_next_computation(self, scheduler):
        entry = scheduler.schedule("scheduled_pipeline", trigger="cron:0 3 * * *")
        # Should compute a next_run in the future
        if entry.next_run:
            assert entry.next_run > time.time() - 10


# ============================================================
# Integration
# ============================================================

class TestIntegration:
    """端到端集成测试。"""

    def test_full_pipeline_flow(self):
        # Create pipeline
        cfg = PipelineConfig(
            name="integration_test",
            transforms=["calc_return"],
            validate=True,
        )
        pipeline = FeaturePipeline(cfg)

        # Register transform
        def calc_return(data):
            prices = data.get("close", [])
            ret = [0.0]
            for i in range(1, len(prices)):
                if prices[i - 1] and prices[i - 1] != 0:
                    ret.append((prices[i] - prices[i - 1]) / prices[i - 1])
                else:
                    ret.append(0.0)
            return {"return": ret}

        pipeline.register_transform("calc_return", calc_return)

        # Orchestrate
        orch = PipelineOrchestrator()
        orch.register(pipeline)

        # Run
        raw_data = {"close": [100.0, 101.0, 102.0, 103.0, 104.0]}
        result = orch.run("integration_test", raw_data)

        assert result.status == PipelineStatus.COMPLETED
        assert result.feature_count >= 2  # close + return
        assert "return" in result.feature_names

    def test_orchestrator_with_cache(self):
        cache = FeatureCache(policy=CachePolicy.ALWAYS)
        orch = PipelineOrchestrator()

        pipeline = FeaturePipeline(PipelineConfig(name="cached_pipeline"))
        orch.register(pipeline)

        raw_data = {"close": [100.0, 101.0, 102.0]}
        cache.put("close", "2024-01-01", raw_data["close"])

        # Cache hit
        cached = cache.get("close", "2024-01-01")
        assert cached == [100.0, 101.0, 102.0]

        # Run pipeline
        result = orch.run("cached_pipeline", {"close": cached})
        assert result.status == PipelineStatus.COMPLETED
