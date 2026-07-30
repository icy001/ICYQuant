from services.observability import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    MetricData,
    MetricType,
)


class TestCounter:
    def test_increment(self):
        counter = Counter("test_counter", "test_service")
        counter.increment(5)
        assert counter.get() == 5.0

    def test_multiple_increments(self):
        counter = Counter("test_counter", "test_service")
        counter.increment(1)
        counter.increment(2)
        counter.increment(3)
        assert counter.get() == 6.0

    def test_snapshot(self):
        counter = Counter("test_counter", "test_service")
        counter.increment(10)
        snap = counter.snapshot()
        assert snap.name == "test_counter"
        assert snap.value == 10.0
        assert snap.type == MetricType.COUNTER.value


class TestGauge:
    def test_set(self):
        gauge = Gauge("test_gauge", "test_service")
        gauge.set(42.5)
        assert gauge.get() == 42.5

    def test_increment_decrement(self):
        gauge = Gauge("test_gauge", "test_service")
        gauge.set(50)
        gauge.increment(10)
        assert gauge.get() == 60
        gauge.decrement(20)
        assert gauge.get() == 40

    def test_snapshot(self):
        gauge = Gauge("test_gauge", "test_service")
        gauge.set(100)
        snap = gauge.snapshot()
        assert snap.value == 100
        assert snap.type == MetricType.GAUGE.value


class TestHistogram:
    def test_observe(self):
        hist = Histogram("test_hist", "test_service")
        for val in [0.01, 0.05, 0.1, 0.2, 0.5]:
            hist.observe(val)
        assert hist.count == 5
        assert hist.mean > 0

    def test_percentiles(self):
        hist = Histogram("test_hist", "test_service")
        values = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 5.0]
        for v in values:
            hist.observe(v)
        assert hist.p50 > 0
        assert hist.p95 >= hist.p50
        assert hist.p99 >= hist.p95

    def test_snapshot(self):
        hist = Histogram("test_hist", "test_service")
        hist.observe(0.05)
        snap = hist.snapshot()
        assert snap["name"] == "test_hist"
        assert snap["count"] == 1


class TestMetricsRegistry:
    def test_create_counters(self):
        reg = MetricsRegistry()
        c1 = reg.counter("counter1", "svc1")
        c2 = reg.counter("counter1", "svc1")
        assert c1 is c2
        c1.increment(1)
        assert c2.get() == 1

    def test_create_gauges(self):
        reg = MetricsRegistry()
        g = reg.gauge("gauge1", "svc1")
        g.set(99)
        found = reg.get_gauge("gauge1")
        assert found is not None
        assert found.get() == 99

    def test_get_all(self):
        reg = MetricsRegistry()
        reg.counter("c1").increment()
        reg.gauge("g1").set(42)
        data = reg.get_all()
        assert "c1" in data["counters"]
        assert "g1" in data["gauges"]


class TestMetricsCollector:
    def test_collect(self):
        collector = MetricsCollector()
        metric = MetricData(
            name="test",
            value=1.0,
            type=MetricType.GAUGE.value,
            service="test_svc",
        )
        collector.collect(metric)
        assert len(collector.all()) == 1

    def test_counter(self):
        collector = MetricsCollector()
        c = collector.counter("test_count", "svc")
        c.increment(5)
        assert c.get() == 5

    def test_gauge(self):
        collector = MetricsCollector()
        g = collector.gauge("test_gauge", "svc")
        g.set(42)
        assert g.get() == 42

    def test_snapshot(self):
        collector = MetricsCollector()
        collector.counter("c1").increment(3)
        collector.gauge("g1").set(100)
        snap = collector.snapshot()
        assert "c1" in snap["counters"]
        assert "g1" in snap["gauges"]
