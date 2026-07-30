"""Tests for Inference Engine — online & batch prediction."""
import pytest
import numpy as np
from services.serving.inference import InferenceEngine, InferenceConfig, BatchInferenceRequest, BatchInferenceResult


class MockModel:
    def predict(self, features):
        if isinstance(features, np.ndarray):
            return np.array([0.82])
        return 0.82

    def predict_proba(self, features):
        if isinstance(features, np.ndarray):
            return np.array([[0.15, 0.85]])
        return [0.15, 0.85]


class MockModelEnsemble:
    def __init__(self):
        self.estimators_ = [MockModel() for _ in range(5)]

    def predict(self, features):
        if isinstance(features, np.ndarray):
            return np.array([0.75])
        return 0.75

    @property
    def feature_names_(self):
        return None


class TestInferenceEngine:
    def test_predict_single(self):
        engine = InferenceEngine(InferenceConfig(enable_confidence=False))
        model = MockModel()
        pred, conf = engine.predict(model, {"a": 1.0, "b": 2.0})
        assert pred == 0.82

    def test_predict_with_proba(self):
        engine = InferenceEngine(InferenceConfig(enable_confidence=True))
        model = MockModel()
        pred, conf = engine.predict(model, {"a": 1.0, "b": 2.0})
        assert pred == 0.85
        assert conf is not None
        assert 0 <= conf <= 1.0

    def test_predict_batch(self):
        engine = InferenceEngine(InferenceConfig(batch_size=32))
        model = MockModel()
        features_list = [{"a": float(i)} for i in range(5)]
        result = engine.predict_batch(model, features_list, symbols=["S1", "S2", "S3", "S4", "S5"])
        assert len(result.predictions) == 5
        assert len(result.symbols) == 5
        assert result.latency_ms >= 0

    def test_predict_empty_features_raises(self):
        engine = InferenceEngine(InferenceConfig())
        model = MockModel()
        with pytest.raises(ValueError):
            engine.predict(model, {})

    def test_predict_nan_feature_raises(self):
        engine = InferenceEngine(InferenceConfig())
        model = MockModel()
        with pytest.raises(ValueError):
            engine.predict(model, {"a": float("nan")})

    def test_predict_inf_feature_raises(self):
        engine = InferenceEngine(InferenceConfig())
        model = MockModel()
        with pytest.raises(ValueError):
            engine.predict(model, {"a": float("inf")})

    def test_predict_non_numeric_raises(self):
        engine = InferenceEngine(InferenceConfig())
        model = MockModel()
        with pytest.raises(TypeError):
            engine.predict(model, {"a": "string"})

    def test_warmup(self):
        engine = InferenceEngine(InferenceConfig(warmup_iterations=3))
        model = MockModel()
        engine.warmup(model, {"a": 1.0, "b": 2.0}, model_name="test")
        assert engine._warmed_up.get("test") is True

    def test_ensemble_confidence(self):
        engine = InferenceEngine(InferenceConfig(enable_confidence=True))
        model = MockModelEnsemble()
        pred, conf = engine.predict(model, {"a": 1.0})
        assert conf is not None
        assert 0 <= conf <= 1.0

    def test_batch_result_to_dict(self):
        result = BatchInferenceResult(
            predictions=[0.1, 0.2],
            confidences=[0.9, 0.8],
            symbols=["A", "B"],
            latency_ms=5.0,
            model_name="test",
        )
        d = result.to_dict()
        assert d["predictions"] == [0.1, 0.2]
        assert d["latency_ms"] == 5.0

    def test_config_defaults(self):
        config = InferenceConfig()
        assert config.batch_size == 64
        assert config.timeout_ms == 500
        assert config.enable_confidence is True
