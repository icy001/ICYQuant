from services.observability import (
    AIMonitor,
    AIServiceStatus,
    ModelHealth,
    AIHealthStatus,
    GPUMonitor,
    GPUClusterStatus,
    GPUStats,
    InferenceMonitor,
    InferenceMetrics,
    CostAnalyzer,
    CostBreakdown,
)


class TestAIMonitor:
    def test_register_model(self):
        monitor = AIMonitor()
        monitor.register_model("gpt-4", "LLM")
        health = monitor.get_model_health("gpt-4")
        assert health is not None
        assert health.model_name == "gpt-4"

    def test_update_health_healthy(self):
        monitor = AIMonitor()
        monitor.register_model("test-model", "LLM")
        health = monitor.update_health("test-model", 50, 0.01, 100)
        assert health.status == AIHealthStatus.HEALTHY.value

    def test_update_health_degraded(self):
        monitor = AIMonitor()
        monitor.register_model("test-model", "LLM")
        health = monitor.update_health("test-model", 600, 0.01, 100)
        assert health.status == AIHealthStatus.DEGRADED.value

    def test_update_health_unhealthy(self):
        monitor = AIMonitor()
        monitor.register_model("test-model", "LLM")
        health = monitor.update_health("test-model", 50, 0.10, 100)
        assert health.status == AIHealthStatus.UNHEALTHY.value

    def test_service_status(self):
        monitor = AIMonitor()
        monitor.register_model("model1", "LLM")
        monitor.register_model("model2", "EMBEDDING")
        monitor.update_health("model1", 50, 0.01, 100)
        monitor.update_health("model2", 30, 0.02, 200)
        status = monitor.get_service_status()
        assert status.overall_status == AIHealthStatus.HEALTHY.value

    def test_service_status_unhealthy(self):
        monitor = AIMonitor()
        monitor.register_model("model1", "LLM")
        monitor.register_model("model2", "EMBEDDING")
        monitor.update_health("model1", 50, 0.10, 100)
        monitor.update_health("model2", 30, 0.02, 200)
        status = monitor.get_service_status()
        assert status.overall_status == AIHealthStatus.UNHEALTHY.value

    def test_check_model(self):
        monitor = AIMonitor()
        result = monitor.check_model("nonexistent")
        assert result["status"] == "NOT_FOUND"


class TestGPUMonitor:
    def test_register_gpu(self):
        monitor = GPUMonitor()
        monitor.register_gpu(0, "RTX 4090", 24576)
        gpu = monitor.get_gpu(0)
        assert gpu is not None
        assert gpu.gpu_id == 0

    def test_update_stats(self):
        monitor = GPUMonitor()
        monitor.register_gpu(0, "RTX 4090", 24576)
        stats = monitor.update_stats(0, 75.5, 12288, 65.0, 350.0)
        assert stats.utilization_pct == 75.5
        assert stats.is_healthy is True

    def test_overloaded_gpu(self):
        monitor = GPUMonitor()
        monitor.register_gpu(0, "GPU", 24576)
        monitor.update_stats(0, 95, 24000, 90, 400)
        overloaded = monitor.get_overloaded_gpus()
        assert len(overloaded) >= 1

    def test_cluster_status(self):
        monitor = GPUMonitor()
        monitor.register_gpu(0, "GPU0", 24576)
        monitor.register_gpu(1, "GPU1", 24576)
        monitor.update_stats(0, 50, 10000, 55, 300)
        monitor.update_stats(1, 60, 12000, 60, 300)
        status = monitor.get_cluster_status()
        assert status.total_gpus == 2
        assert status.healthy_gpus == 2
        assert status.status == "HEALTHY"

    def test_best_available_gpu(self):
        monitor = GPUMonitor()
        monitor.register_gpu(0, "GPU0", 24576)
        monitor.register_gpu(1, "GPU1", 24576)
        monitor.update_stats(0, 80, 20000, 70, 350)
        monitor.update_stats(1, 30, 5000, 50, 250)
        best = monitor.get_best_available_gpu(8000)
        assert best is not None
        assert best.gpu_id == 1


class TestInferenceMonitor:
    def test_start_complete_request(self):
        monitor = InferenceMonitor()
        monitor.register_model("test-model")
        req = monitor.start_request("req1", "test-model")
        assert req.status == "PENDING"
        monitor.complete_request("req1", tokens_used=100, success=True)
        completed = monitor.get_request("req1")
        assert completed.status == "SUCCESS"
        assert completed.latency_ms > 0

    def test_timeout_request(self):
        monitor = InferenceMonitor()
        monitor.register_model("test-model")
        monitor.start_request("req1", "test-model")
        monitor.complete_request("req1", timeout=True, error="Request timed out")
        completed = monitor.get_request("req1")
        assert completed.status == "TIMEOUT"

    def test_get_metrics(self):
        monitor = InferenceMonitor()
        monitor.register_model("test-model")
        for i in range(10):
            req = monitor.start_request(f"req_{i}", "test-model")
            monitor.complete_request(f"req_{i}", tokens_used=50 + i * 10, success=True)
        metrics = monitor.get_metrics("test-model")
        assert metrics.total_requests == 10
        assert metrics.success_rate >= 0.9

    def test_get_all_model_metrics(self):
        monitor = InferenceMonitor()
        monitor.register_model("model-a")
        monitor.register_model("model-b")
        monitor.start_request("r1", "model-a")
        monitor.complete_request("r1", success=True)
        metrics = monitor.get_all_model_metrics()
        assert len(metrics) == 2


class TestCostAnalyzer:
    def test_record_cost(self):
        analyzer = CostAnalyzer()
        entry = analyzer.record_cost("GPU", "GPU_0", 2.0, 25.0)
        assert entry.amount == 50.0
        assert entry.resource_type == "GPU"

    def test_record_gpu_cost(self):
        analyzer = CostAnalyzer()
        entry = analyzer.record_gpu_cost(0, 4.0, 30.0)
        assert entry.amount == 120.0

    def test_record_api_cost(self):
        analyzer = CostAnalyzer()
        entry = analyzer.record_api_cost("openai", "gpt-4", 100000, 0.003)
        assert entry.amount == 0.3
        assert entry.resource_type == "API"

    def test_get_breakdown(self):
        analyzer = CostAnalyzer()
        analyzer.record_cost("GPU", "GPU_0", 2, 25)
        analyzer.record_cost("STORAGE", "S3", 100, 0.15)
        breakdown = analyzer.get_breakdown()
        assert breakdown.total_amount > 0
        assert breakdown.entries_count == 2

    def test_get_daily_cost(self):
        analyzer = CostAnalyzer()
        analyzer.record_cost("GPU", "GPU_0", 2, 25)
        daily = analyzer.get_daily_cost()
        assert daily.total_amount == 50.0

    def test_get_cost_summary(self):
        analyzer = CostAnalyzer()
        analyzer.record_cost("GPU", "GPU_0", 2, 25)
        analyzer.record_cost("API", "openai", 1, 100)
        summary = analyzer.get_cost_summary()
        assert "GPU" in summary
        assert "API" in summary

    def test_monthly_report(self):
        analyzer = CostAnalyzer()
        analyzer.record_cost("GPU", "GPU_0", 2, 25)
        report = analyzer.generate_monthly_report(2026, 7)
        assert report.total_cost > 0
        assert report.month == "2026-07"

    def test_total_cost(self):
        analyzer = CostAnalyzer()
        analyzer.record_cost("GPU", "GPU_0", 2, 25)
        analyzer.record_cost("API", "api", 1, 100)
        assert analyzer.get_total_cost() == 150.0
