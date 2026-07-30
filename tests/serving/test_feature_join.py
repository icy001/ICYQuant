"""Tests for Online Feature Join."""
import pytest
from services.serving.feature_join import (
    FeatureJoiner, JoinSpec, JoinResult, JoinStrategy,
)


class MockOnlineStore:
    def __init__(self, data=None):
        self.data = data or {}

    def get_feature(self, entity_id, feature_name):
        record = self.data.get(entity_id, {})
        return record.get(feature_name)

    def get(self, entity_id):
        class MockRecord:
            def __init__(self, features):
                self.features = features
        return MockRecord(self.data.get(entity_id, {}))


class TestFeatureJoiner:
    def test_join_with_spec(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3, "atr14": 4.1, "rsi14": 62.5}})
        joiner = FeatureJoiner(online_store=store)
        spec = JoinSpec(feature_names=["ema20", "atr14", "rsi14"])
        result = joiner.join("NVDA", spec=spec)
        assert result.entity_id == "NVDA"
        assert result.features["ema20"] == 182.3
        assert result.features["atr14"] == 4.1
        assert result.complete is True

    def test_join_missing_features(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3}})
        joiner = FeatureJoiner(online_store=store)
        spec = JoinSpec(feature_names=["ema20", "atr14", "rsi14"])
        result = joiner.join("NVDA", spec=spec)
        assert result.features["ema20"] == 182.3
        assert "atr14" in result.missing_features
        assert "rsi14" in result.missing_features
        assert result.complete is False

    def test_join_with_model_features(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3, "atr14": 4.1}})
        joiner = FeatureJoiner(online_store=store)
        joiner.register_model_features("alpha_us", ["ema20", "atr14"])
        spec = JoinSpec(model_name="alpha_us")
        result = joiner.join("NVDA", spec=spec)
        assert result.features["ema20"] == 182.3
        assert result.feature_count == 2

    def test_join_with_feature_group(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3, "ema50": 180.1}})
        joiner = FeatureJoiner(online_store=store)
        joiner.register_feature_group("ema", ["ema20", "ema50"])
        spec = JoinSpec(feature_group="ema")
        result = joiner.join("NVDA", spec=spec)
        assert result.features["ema20"] == 182.3
        assert result.features["ema50"] == 180.1

    def test_join_exclude_features(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3, "atr14": 4.1, "rsi14": 62.5}})
        joiner = FeatureJoiner(online_store=store)
        spec = JoinSpec(feature_names=["ema20", "atr14", "rsi14"], exclude=["rsi14"])
        result = joiner.join("NVDA", spec=spec)
        assert "rsi14" not in result.features
        assert result.feature_count == 2

    def test_join_batch(self):
        store = MockOnlineStore({
            "NVDA": {"ema20": 182.3},
            "AAPL": {"ema20": 175.1},
        })
        joiner = FeatureJoiner(online_store=store)
        spec = JoinSpec(feature_names=["ema20"])
        results = joiner.join_batch(["NVDA", "AAPL"], spec=spec)
        assert len(results) == 2
        assert results[0].features["ema20"] == 182.3
        assert results[1].features["ema20"] == 175.1

    def test_join_no_store_mock_fallback(self):
        joiner = FeatureJoiner()  # no online store
        spec = JoinSpec(feature_names=["ema20", "atr14"])
        result = joiner.join("NVDA", spec=spec)
        assert result.feature_count == 2

    def test_join_result_latency(self):
        joiner = FeatureJoiner()
        spec = JoinSpec(feature_names=["ema20"])
        result = joiner.join("NVDA", spec=spec)
        assert result.latency_ms >= 0

    def test_join_result_to_dict(self):
        result = JoinResult(
            entity_id="NVDA",
            features={"ema20": 182.3},
            source="online_only",
        )
        d = result.to_dict()
        assert d["entity_id"] == "NVDA"
        assert d["feature_count"] == 1
        assert d["complete"] is True

    def test_join_online_fallback_strategy(self):
        store = MockOnlineStore({"NVDA": {"ema20": 182.3}})
        joiner = FeatureJoiner(online_store=store)
        spec = JoinSpec(feature_names=["ema20", "missing_feat"])
        result = joiner.join("NVDA", spec=spec, strategy=JoinStrategy.ONLINE_ONLY)
        assert "missing_feat" in result.missing_features
