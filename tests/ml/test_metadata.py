"""Tests for ML metadata management."""

from services.ml.metadata import (
    ModelMetadata,
    MetadataManager,
    ModelFramework,
    ModelStage,
)


class TestModelMetadata:
    """Tests for ModelMetadata dataclass."""

    def test_create_metadata(self):
        """创建模型元数据应正确保存所有字段。"""
        meta = ModelMetadata(
            model_name="alpha_model",
            version="v4",
            author="researcher_01",
            framework=ModelFramework.LIGHTGBM,
            dataset="US_STOCK_2025",
            features=["momentum_20", "volatility_60", "volume_ratio"],
            target="next_day_return",
            hyperparameters={"learning_rate": 0.05, "max_depth": 6},
            metrics={"sharpe": 2.03, "accuracy": 0.742},
            git_commit="abc123def",
        )
        assert meta.model_name == "alpha_model"
        assert meta.version == "v4"
        assert meta.author == "researcher_01"
        assert meta.framework == ModelFramework.LIGHTGBM
        assert meta.dataset == "US_STOCK_2025"
        assert len(meta.features) == 3
        assert meta.target == "next_day_return"
        assert meta.hyperparameters["learning_rate"] == 0.05
        assert meta.metrics["sharpe"] == 2.03
        assert meta.git_commit == "abc123def"
        assert meta.stage == ModelStage.DEVELOPMENT

    def test_default_values(self):
        """默认值应正确设置。"""
        meta = ModelMetadata(model_name="test_model", version="v1")
        assert meta.author == "unknown"
        assert meta.framework == ModelFramework.LIGHTGBM
        assert meta.stage == ModelStage.DEVELOPMENT
        assert meta.dataset == ""
        assert meta.features == []
        assert meta.created_at != ""

    def test_to_dict(self):
        """to_dict 应正确序列化。"""
        meta = ModelMetadata(
            model_name="alpha_model",
            version="v4",
            framework=ModelFramework.XGBOOST,
            features=["f1", "f2"],
            metrics={"accuracy": 0.85},
        )
        d = meta.to_dict()
        assert d["model_name"] == "alpha_model"
        assert d["version"] == "v4"
        assert d["framework"] == "XGBoost"
        assert d["features"] == ["f1", "f2"]
        assert d["metrics"] == {"accuracy": 0.85}

    def test_from_dict(self):
        """from_dict 应正确反序列化。"""
        data = {
            "model_name": "test_model",
            "version": "v2",
            "framework": "PyTorch",
            "stage": "Production",
            "features": ["f_a"],
        }
        meta = ModelMetadata.from_dict(data)
        assert meta.model_name == "test_model"
        assert meta.version == "v2"
        assert meta.framework == ModelFramework.PYTORCH
        assert meta.stage == ModelStage.PRODUCTION

    def test_metadata_id_unique(self):
        """两个不同的元数据应具有不同的 ID。"""
        m1 = ModelMetadata(model_name="m1", version="v1")
        m2 = ModelMetadata(model_name="m2", version="v1")
        assert m1.metadata_id != m2.metadata_id

    def test_metadata_stages(self):
        """模型阶段枚举应包含所有五个阶段。"""
        stages = list(ModelStage)
        assert len(stages) == 5
        assert ModelStage.DEVELOPMENT in stages
        assert ModelStage.TESTING in stages
        assert ModelStage.STAGING in stages
        assert ModelStage.PRODUCTION in stages
        assert ModelStage.ARCHIVED in stages

    def test_frameworks(self):
        """应支持多种 ML 框架。"""
        frameworks = list(ModelFramework)
        assert ModelFramework.LIGHTGBM in frameworks
        assert ModelFramework.XGBOOST in frameworks
        assert ModelFramework.PYTORCH in frameworks
        assert ModelFramework.TENSORFLOW in frameworks


class TestMetadataManager:
    """Tests for MetadataManager."""

    def test_save_and_get(self):
        """保存和检索元数据应正常。"""
        mgr = MetadataManager()
        meta = ModelMetadata(model_name="alpha_model", version="v4")
        mgr.save(meta)
        assert mgr.get(meta.metadata_id) is not None
        assert mgr.get(meta.metadata_id).model_name == "alpha_model"

    def test_save_updates_existing(self):
        """更新已有元数据（相同名称+版本）应覆盖。"""
        mgr = MetadataManager()
        meta = ModelMetadata(model_name="alpha_model", version="v4", dataset="old")
        mgr.save(meta)
        meta2 = ModelMetadata(model_name="alpha_model", version="v4", dataset="new")
        mgr.save(meta2)
        result = mgr.get_by_name_version("alpha_model", "v4")
        assert result is not None
        assert result.dataset == "new"

    def test_get_by_name_version(self):
        """按名称和版本查找应正确。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="alpha_model", version="v3"))
        mgr.save(ModelMetadata(model_name="alpha_model", version="v4"))
        v4 = mgr.get_by_name_version("alpha_model", "v4")
        assert v4 is not None
        assert v4.version == "v4"

    def test_get_nonexistent(self):
        """不存在的检索应返回 None。"""
        mgr = MetadataManager()
        assert mgr.get("nonexistent") is None
        assert mgr.get_by_name_version("no_model", "v1") is None

    def test_delete(self):
        """删除元数据应正常。"""
        mgr = MetadataManager()
        meta = ModelMetadata(model_name="to_delete", version="v1")
        mgr.save(meta)
        assert mgr.count() == 1
        assert mgr.delete(meta.metadata_id)
        assert mgr.count() == 0
        assert mgr.get(meta.metadata_id) is None

    def test_delete_nonexistent(self):
        """删除不存在的条目应返回 False。"""
        mgr = MetadataManager()
        assert mgr.delete("fake_id") is False

    def test_list_by_model(self):
        """按模型名称列表应返回所有版本（最新的在前）。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="test", version="v1"))
        mgr.save(ModelMetadata(model_name="test", version="v2"))
        mgr.save(ModelMetadata(model_name="test", version="v3"))
        versions = mgr.list_by_model("test")
        assert len(versions) == 3
        assert versions[0].version == "v3"

    def test_list_all(self):
        """list_all 应返回所有条目。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="m1", version="v1"))
        mgr.save(ModelMetadata(model_name="m2", version="v1"))
        assert len(mgr.list_all()) == 2

    def test_list_by_stage(self):
        """按阶段过滤应正确。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="prod", version="v1", stage=ModelStage.PRODUCTION))
        mgr.save(ModelMetadata(model_name="dev", version="v1", stage=ModelStage.DEVELOPMENT))
        mgr.save(ModelMetadata(model_name="dev2", version="v1", stage=ModelStage.DEVELOPMENT))
        prod_models = mgr.list_by_stage(ModelStage.PRODUCTION)
        assert len(prod_models) == 1
        assert prod_models[0].model_name == "prod"

    def test_list_by_framework(self):
        """按框架过滤应正确。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="lgb", version="v1", framework=ModelFramework.LIGHTGBM))
        mgr.save(ModelMetadata(model_name="xgb", version="v1", framework=ModelFramework.XGBOOST))
        lgb = mgr.list_by_framework(ModelFramework.LIGHTGBM)
        assert len(lgb) == 1

    def test_update_stage(self):
        """更新阶段应正确。"""
        mgr = MetadataManager()
        meta = ModelMetadata(model_name="test", version="v1")
        mgr.save(meta)
        result = mgr.update_stage("test", "v1", ModelStage.TESTING)
        assert result is not None
        assert result.stage == ModelStage.TESTING

    def test_update_stage_nonexistent(self):
        """更新不存在的条目应返回 None。"""
        mgr = MetadataManager()
        result = mgr.update_stage("no", "v1", ModelStage.PRODUCTION)
        assert result is None

    def test_get_latest_version(self):
        """获取最新版本应正确。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="test", version="v1"))
        mgr.save(ModelMetadata(model_name="test", version="v5"))
        latest = mgr.get_latest_version("test")
        assert latest is not None
        assert latest.version == "v5"

    def test_get_latest_version_empty(self):
        """空列表查询应返回 None。"""
        mgr = MetadataManager()
        assert mgr.get_latest_version("not_exist") is None

    def test_get_production_model(self):
        """获取生产模型应正确。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="test", version="v1", stage=ModelStage.DEVELOPMENT))
        mgr.save(ModelMetadata(model_name="test", version="v3", stage=ModelStage.PRODUCTION))
        prod = mgr.get_production_model("test")
        assert prod is not None
        assert prod.version == "v3"

    def test_get_production_model_none(self):
        """不存在生产模型时应返回 None。"""
        mgr = MetadataManager()
        mgr.save(ModelMetadata(model_name="test", version="v1", stage=ModelStage.DEVELOPMENT))
        assert mgr.get_production_model("test") is None

    def test_count(self):
        """计数应正确。"""
        mgr = MetadataManager()
        assert mgr.count() == 0
        mgr.save(ModelMetadata(model_name="a", version="v1"))
        mgr.save(ModelMetadata(model_name="b", version="v1"))
        assert mgr.count() == 2
