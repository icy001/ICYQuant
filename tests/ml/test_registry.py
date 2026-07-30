"""Tests for Model Registry."""

import pytest
from services.ml.registry import ModelRegistry, ModelVersion, RegistryEntry
from services.ml.metadata import ModelMetadata, ModelStage, ModelFramework


class TestModelVersion:
    """Tests for ModelVersion dataclass."""

    def test_create_version(self):
        """创建模型版本应正确设置字段。"""
        mv = ModelVersion(version="v4", stage=ModelStage.DEVELOPMENT)
        assert mv.version == "v4"
        assert mv.stage == ModelStage.DEVELOPMENT
        assert mv.registered_at != ""

    def test_version_to_dict(self):
        """to_dict 应正确序列化。"""
        meta = ModelMetadata(model_name="test", version="v1")
        mv = ModelVersion(
            version="v4",
            stage=ModelStage.PRODUCTION,
            metadata=meta,
            experiment_id="exp_001",
            metrics={"sharpe": 2.5},
        )
        d = mv.to_dict()
        assert d["version"] == "v4"
        assert d["stage"] == "Production"
        assert d["experiment_id"] == "exp_001"
        assert d["metadata"] is not None

    def test_version_without_metadata(self):
        """不带元数据的版本应正确序列化。"""
        mv = ModelVersion(version="v1")
        d = mv.to_dict()
        assert d["metadata"] is None


class TestRegistryEntry:
    """Tests for RegistryEntry dataclass."""

    def test_create_entry(self):
        """创建注册表条目应正确。"""
        entry = RegistryEntry(model_name="alpha_model")
        assert entry.model_name == "alpha_model"
        assert entry.versions == []
        assert entry.latest_version == ""

    def test_entry_to_dict(self):
        """to_dict 应包含版本。"""
        entry = RegistryEntry(
            model_name="alpha_model",
            versions=[ModelVersion(version="v1"), ModelVersion(version="v2")],
            latest_version="v2",
            description="Alpha signal model",
            tags={"type": "alpha"},
        )
        d = entry.to_dict()
        assert d["model_name"] == "alpha_model"
        assert len(d["versions"]) == 2
        assert d["latest_version"] == "v2"


class TestModelRegistry:
    """Tests for ModelRegistry."""

    def test_register_model(self):
        """注册模型应正确。"""
        registry = ModelRegistry()
        meta = ModelMetadata(model_name="alpha_model", version="v4")
        entry = registry.register("alpha_model", "v4", metadata=meta)
        assert entry.model_name == "alpha_model"
        assert entry.latest_version == "v4"
        assert len(entry.versions) == 1

    def test_register_duplicate_version_fails(self):
        """注册相同版本应抛出 ValueError。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        with pytest.raises(ValueError, match="already exists"):
            registry.register("alpha_model", "v4")

    def test_register_multiple_versions(self):
        """同一模型可注册多个版本。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v1")
        registry.register("alpha_model", "v2")
        registry.register("alpha_model", "v3")
        entry = registry.get("alpha_model")
        assert entry is not None
        assert len(entry.versions) == 3
        assert entry.latest_version == "v3"

    def test_register_different_models(self):
        """不同名称的模型可共存。"""
        registry = ModelRegistry()
        registry.register("model_a", "v1")
        registry.register("model_b", "v1")
        assert registry.count() == 2

    def test_get_nonexistent_model(self):
        """不存在的模型应返回 None。"""
        registry = ModelRegistry()
        assert registry.get("unknown") is None

    def test_get_version(self):
        """获取特定版本应正确。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v3")
        registry.register("alpha_model", "v4")
        v3 = registry.get_version("alpha_model", "v3")
        assert v3 is not None
        assert v3.version == "v3"

    def test_get_version_nonexistent(self):
        """不存在的版本应返回 None。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v1")
        assert registry.get_version("alpha_model", "v999") is None
        assert registry.get_version("unknown_model", "v1") is None

    def test_promote_forward(self):
        """向前推进阶段应成功。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        assert registry.promote("alpha_model", "v4", ModelStage.TESTING)
        mv = registry.get_version("alpha_model", "v4")
        assert mv.stage == ModelStage.TESTING
        assert mv.promoted_at is not None

    def test_promote_to_production_with_metadata(self):
        """晋升到 Production 应同时更新元数据阶段。"""
        registry = ModelRegistry()
        meta = ModelMetadata(model_name="alpha_model", version="v4")
        registry.register("alpha_model", "v4", metadata=meta)
        registry.promote("alpha_model", "v4", ModelStage.TESTING)
        registry.promote("alpha_model", "v4", ModelStage.STAGING)
        registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
        mv = registry.get_version("alpha_model", "v4")
        assert mv.stage == ModelStage.PRODUCTION
        if mv.metadata:
            assert mv.metadata.stage == ModelStage.PRODUCTION

    def test_promote_backward_fails(self):
        """向后降级应抛出异常。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        registry.promote("alpha_model", "v4", ModelStage.STAGING)
        with pytest.raises(ValueError, match="Cannot demote"):
            registry.promote("alpha_model", "v4", ModelStage.DEVELOPMENT)

    def test_promote_nonexistent_fails(self):
        """晋升不存在的模型应抛出异常。"""
        registry = ModelRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.promote("no_model", "v1", ModelStage.PRODUCTION)

    def test_auto_archive_previous_production(self):
        """晋升新版本到 Production 时，旧 Production 版本应自动归档。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v3")
        registry.register("alpha_model", "v4")
        # Promote v3 to production
        registry.promote("alpha_model", "v3", ModelStage.TESTING)
        registry.promote("alpha_model", "v3", ModelStage.STAGING)
        registry.promote("alpha_model", "v3", ModelStage.PRODUCTION)
        assert registry.get_version("alpha_model", "v3").stage == ModelStage.PRODUCTION
        # Now promote v4 to production
        registry.promote("alpha_model", "v4", ModelStage.TESTING)
        registry.promote("alpha_model", "v4", ModelStage.STAGING)
        registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
        assert registry.get_version("alpha_model", "v4").stage == ModelStage.PRODUCTION
        assert registry.get_version("alpha_model", "v3").stage == ModelStage.ARCHIVED

    def test_demote(self):
        """降级操作应正确（用于回滚）。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
        assert registry.demote("alpha_model", "v4", ModelStage.STAGING)
        assert registry.get_version("alpha_model", "v4").stage == ModelStage.STAGING

    def test_demote_nonexistent(self):
        """降级不存在的模型应抛出异常。"""
        registry = ModelRegistry()
        with pytest.raises(ValueError):
            registry.demote("no_model", "v1", ModelStage.DEVELOPMENT)

    def test_archive(self):
        """归档操作应正确。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        assert registry.archive("alpha_model", "v4")
        assert registry.get_version("alpha_model", "v4").stage == ModelStage.ARCHIVED

    def test_get_production(self):
        """获取生产模型应正确。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v3")
        registry.register("alpha_model", "v4")
        registry.promote("alpha_model", "v4", ModelStage.TESTING)
        registry.promote("alpha_model", "v4", ModelStage.STAGING)
        registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
        prod = registry.get_production("alpha_model")
        assert prod is not None
        assert prod.version == "v4"

    def test_get_production_none(self):
        """没有生产模型时应返回 None。"""
        registry = ModelRegistry()
        assert registry.get_production("unknown") is None

    def test_get_latest(self):
        """获取最新版本应正确。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v1")
        registry.register("alpha_model", "v3")
        latest = registry.get_latest("alpha_model")
        assert latest is not None
        assert latest.version == "v3"

    def test_get_latest_none(self):
        """不存在模型时应返回 None。"""
        registry = ModelRegistry()
        assert registry.get_latest("unknown") is None

    def test_list_by_stage(self):
        """按阶段列出应正确。"""
        registry = ModelRegistry()
        registry.register("m1", "v1")
        registry.register("m2", "v1")
        registry.promote("m1", "v1", ModelStage.TESTING)
        registry.promote("m1", "v1", ModelStage.PRODUCTION)
        test_models = registry.list_by_stage(ModelStage.TESTING)
        assert len(test_models) == 0
        prod_models = registry.list_by_stage(ModelStage.PRODUCTION)
        assert len(prod_models) == 1
        assert prod_models[0].version == "v1"

    def test_promotion_history(self):
        """晋升历史应被记录。"""
        registry = ModelRegistry()
        registry.register("alpha_model", "v4")
        registry.promote("alpha_model", "v4", ModelStage.TESTING)
        registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
        history = registry.get_promotion_history()
        assert len(history) >= 2

    def test_count_and_version_count(self):
        """计数值应正确。"""
        registry = ModelRegistry()
        assert registry.count() == 0
        assert registry.version_count() == 0
        registry.register("a", "v1")
        registry.register("a", "v2")
        registry.register("b", "v1")
        assert registry.count() == 2
        assert registry.version_count() == 3

    def test_full_lifecycle(self):
        """完整生命周期流程：Development → Testing → Staging → Production → Archived。"""
        registry = ModelRegistry()
        meta = ModelMetadata(model_name="full_model", version="v1")
        registry.register("full_model", "v1", metadata=meta)

        stages = [ModelStage.TESTING, ModelStage.STAGING, ModelStage.PRODUCTION]
        for stage in stages:
            assert registry.promote("full_model", "v1", stage)
            mv = registry.get_version("full_model", "v1")
            assert mv.stage == stage

        assert registry.archive("full_model", "v1")
        assert registry.get_version("full_model", "v1").stage == ModelStage.ARCHIVED

    def test_register_with_experiment_and_artifacts(self):
        """注册模型时应可关联实验和制品。"""
        registry = ModelRegistry()
        entry = registry.register(
            "alpha_model",
            "v4",
            experiment_id="exp_001",
            artifact_ids=["art_001", "art_002"],
            metrics={"sharpe": 2.03, "accuracy": 0.742},
        )
        mv = registry.get_version("alpha_model", "v4")
        assert mv.experiment_id == "exp_001"
        assert len(mv.artifact_ids) == 2
        assert mv.metrics["sharpe"] == 2.03
