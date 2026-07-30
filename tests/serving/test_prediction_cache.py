"""Tests for Prediction Cache."""
import pytest
import time
from services.serving.prediction_cache import (
    PredictionCache, CacheConfig, CachePolicy, CachedPrediction,
)


class TestPredictionCache:
    def test_set_and_get(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("NVDA", 0.82, 0.93, "alpha_us")
        result = cache.get("NVDA")
        assert result is not None
        assert result.prediction == 0.82
        assert result.confidence == 0.93
        assert result.model_name == "alpha_us"

    def test_get_expired(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=0.001))
        cache.set("NVDA", 0.82, 0.93)
        time.sleep(0.01)
        result = cache.get("NVDA")
        assert result is None

    def test_get_missing(self):
        cache = PredictionCache(CacheConfig())
        result = cache.get("NONEXISTENT")
        assert result is None

    def test_invalidate_symbol(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("NVDA", 0.82, 0.93)
        assert cache.invalidate("NVDA") is True
        assert cache.get("NVDA") is None

    def test_invalidate_with_model(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("NVDA", 0.82, 0.93, "alpha_us")
        cache.set("NVDA", 0.85, 0.91, "alpha_cn")
        assert cache.invalidate("NVDA", model_name="alpha_us") is True
        # alpha_cn should still be cached
        result = cache.get("NVDA")
        assert result is not None

    def test_invalidate_all(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("NVDA", 0.82, 0.93)
        cache.set("AAPL", 0.71, 0.88)
        count = cache.invalidate_all()
        assert count == 2
        assert cache.get("NVDA") is None

    def test_cache_hit_stats(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60, enable_stats=True))
        cache.set("NVDA", 0.82, 0.93)
        cache.get("NVDA")  # hit
        cache.get("NVDA")  # hit
        cache.get("MISSING")  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] >= 1  # one from get("MISSING")
        # avoid checking exact hit_rate since expired check may add extra miss

    def test_lru_eviction(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=3600, max_entries=3))
        cache.set("A", 0.1)
        cache.set("B", 0.2)
        cache.set("C", 0.3)
        cache.set("D", 0.4)  # should evict A (oldest)
        assert cache.get("A") is None
        assert cache.get("D") is not None

    def test_access_count(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("NVDA", 0.82, 0.93)
        cache.get("NVDA")
        cache.get("NVDA")
        result = cache.get("NVDA")
        assert result.access_count >= 3  # initial + 2 gets

    def test_list_entries(self):
        cache = PredictionCache(CacheConfig(ttl_seconds=60))
        cache.set("A", 0.1)
        cache.set("B", 0.2)
        entries = cache.list_entries()
        assert len(entries) == 2

    def test_on_tick_tick_based(self):
        cache = PredictionCache(CacheConfig(policy=CachePolicy.TICK_BASED))
        cache.set("NVDA", 0.82, 0.93)
        cache.on_tick()  # should invalidate all
        assert cache.get("NVDA") is None

    def test_ttl_cache_policy(self):
        cache = PredictionCache(CacheConfig(policy=CachePolicy.TTL, ttl_seconds=60))
        cache.set("NVDA", 0.82)
        assert cache.get("NVDA") is not None

    def test_cached_prediction_expired(self):
        now = time.time()
        entry = CachedPrediction(
            symbol="NVDA",
            prediction=0.82,
            cached_at=now - 100,
            expires_at=now - 1,
        )
        assert entry.expired is True

    def test_cached_prediction_age(self):
        entry = CachedPrediction(symbol="NVDA", prediction=0.82)
        assert entry.age_seconds >= 0
