"""Validation tests for ICYQuant Service Mesh Observability.

Runs comprehensive validation across all observability components
and reports pass/fail counts.
"""

import asyncio
import sys
import time
import traceback
from typing import Any, Dict, List

sys.path.insert(0, ".")

PASSED = 0
FAILED = 0
FAILURES: List[str] = []


def check(condition: bool, name: str) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        FAILURES.append(f"  - FAIL: {name}")


def report_section(title: str) -> None:
    print(f"\n=== {title} ===")


# ============================================================
# 1. ObservabilityEvents
# ============================================================
async def test_events() -> None:
    report_section("1. Observability Events")
    from infrastructure.service_mesh.observability import (
        ObservabilityEvent, ObservabilityEventPublisher,
    )

    pub = ObservabilityEventPublisher()
    received = []
    pub.subscribe(lambda e: received.append(e))

    pub.publish(ObservabilityEvent.TRACE_COMPLETED, {"trace_id": "t1"})
    pub.publish(ObservabilityEvent.POLICY_CHANGED, {"policy_id": "p1"})
    pub.publish(ObservabilityEvent.SLO_VIOLATION, {"slo_id": "s1"})
    pub.publish(ObservabilityEvent.ANOMALY_DETECTED, {"type": "latency_spike"})

    check(len(received) == 4, "4 events received")
    check(received[0]["event_type"] == "trace_completed", "trace event type")

    # Filtered subscription
    filtered = []
    pub.subscribe(lambda e: filtered.append(e), [ObservabilityEvent.SLO_VIOLATION])
    pub.publish(ObservabilityEvent.SLO_VIOLATION, {"slo_id": "s2"})
    pub.publish(ObservabilityEvent.ANOMALY_DETECTED, {"type": "error_burst"})
    check(len(filtered) == 1, "1 filtered event")
    check(filtered[0]["data"]["slo_id"] == "s2", "filtered event data")

    stats = pub.get_stats()
    check(stats["publish_count"] == 6, "publish count")
    check(stats["stored_events"] == 6, "stored events")

    history = pub.get_history(ObservabilityEvent.TRACE_COMPLETED)
    check(len(history) == 1, "trace history")
    pub.clear()
    check(len(pub.get_history()) == 0, "history cleared")


# ============================================================
# 2. ObservabilityMetrics
# ============================================================
async def test_metrics() -> None:
    report_section("2. Observability Metrics")
    from infrastructure.service_mesh.observability import ObservabilityMetrics

    m = ObservabilityMetrics()
    m.increment_trace({"operation": "rpc"})
    m.increment_span()
    m.increment_policy_eval({"policy_id": "p1"})
    m.increment_slo_violation()
    m.increment_anomaly()
    m.increment_runtime_analysis()
    m.increment_dashboard_request()
    m.increment_access_log()
    m.increment_metrics_flush()
    m.set_active_traces(5)
    m.set_active_spans(10)

    s = m.get_summary()
    check(s["counters"]["icyquant_mesh_trace_total"] == 1, "trace counter")
    check(s["counters"]["icyquant_mesh_span_total"] == 1, "span counter")
    check(s["counters"]["icyquant_mesh_policy_eval_total"] == 1, "policy eval counter")
    check(s["counters"]["icyquant_mesh_slo_violation_total"] == 1, "slo violation counter")
    check(s["counters"]["icyquant_mesh_anomaly_total"] == 1, "anomaly counter")
    check(s["counters"]["icyquant_mesh_runtime_analysis_total"] == 1, "runtime analysis counter")
    check(s["counters"]["icyquant_mesh_dashboard_request_total"] == 1, "dashboard counter")
    check(s["counters"]["icyquant_mesh_access_log_total"] == 1, "access log counter")
    check(s["counters"]["icyquant_mesh_metrics_flush_total"] == 1, "metrics flush counter")
    check(s["gauges"]["icyquant_mesh_active_traces"] == 5.0, "active traces gauge")
    check(s["gauges"]["icyquant_mesh_active_spans"] == 10.0, "active spans gauge")

    m.record_timer("trace_duration", 0.5)
    m.record_timer("trace_duration", 1.5)
    s2 = m.get_summary()
    check("trace_duration" in s2["timer_stats"], "timer stats present")
    check(s2["timer_stats"]["trace_duration"]["count"] == 2, "timer count")

    m.reset()
    s3 = m.get_summary()
    check(s3["counters"]["icyquant_mesh_trace_total"] == 0, "reset works")


# ============================================================
# 3. ObservabilityTelemetry
# ============================================================
async def test_telemetry() -> None:
    report_section("3. Observability Telemetry")
    from infrastructure.service_mesh.observability import ObservabilityTelemetry

    t = ObservabilityTelemetry()
    t.log_trace("trace-1", "rpc", "oms", "risk", 0.5, True)
    t.log_span("span-1", "trace-1", "rpc", 0.1, True)
    t.log_policy_eval("pol-1", "allowed", "spiffe://x", "orders")
    t.log_anomaly("latency_spike", "oms-svc", "critical")
    t.log_slo_violation("slo-1", "latency", 100, 500)
    t.log_runtime_analysis("traffic_pattern", ["scale up"])
    t.log_adaptive_adjustment("rule-1", "increase_timeout", "high latency")
    t.log_dashboard_request("/mesh/overview", 200, 0.01)
    t.log_error("trace_collector", "timeout", "connection timeout")

    events = t.get_events()
    check(len(events) == 9, "9 events logged")
    check(len(t.get_events("trace")) == 1, "trace event filter")
    check(len(t.get_events("span")) == 1, "span event filter")
    check(len(t.get_events("policy_eval")) == 1, "policy eval filter")
    check(len(t.get_events("anomaly")) == 1, "anomaly filter")
    check(len(t.get_events("slo_violation")) == 1, "slo violation filter")
    check(len(t.get_events("error")) == 1, "error filter")

    stats = t.get_stats()
    check(stats["event_count"] == 9, "event count")
    t.clear()
    check(len(t.get_events()) == 0, "cleared")


# ============================================================
# 4. ObservabilityHealth
# ============================================================
async def test_health() -> None:
    report_section("4. Observability Health")
    from infrastructure.service_mesh.observability import ObservabilityHealth

    h = ObservabilityHealth()
    h.register_check("custom", lambda: True)

    result = await h.check()
    check(result["healthy"], "all healthy")
    check("trace_collector" in result["components"], "trace_collector in health")
    check("custom" in result["components"], "custom in health")
    check(result["total"] >= 9, "check count")

    h.register_check("failing", lambda: False)
    result2 = await h.check()
    check(not result2["healthy"], "not all healthy")
    check(result2["components"]["failing"] == False, "failing check")

    stats = h.get_stats()
    check(stats["check_count"] >= 10, "check count stats")


# ============================================================
# 5. ObservabilityDiagnostics
# ============================================================
async def test_diagnostics() -> None:
    report_section("5. Observability Diagnostics")
    from infrastructure.service_mesh.observability import ObservabilityDiagnostics

    d = ObservabilityDiagnostics()
    d.register_trace("t1", {"operation": "rpc"})
    d.register_trace("t2", {"operation": "kafka"})
    d.record_policy_evaluation("p1", "spiffe://x", "allowed")
    d.record_anomaly("latency_spike", "oms", "warning")
    d.record_analysis("traffic_pattern", ["scale up"])

    snap = d.get_snapshot()
    check(snap["trace_count"] == 2, "trace count")
    check(snap["policy_evaluation_count"] == 1, "policy eval count")
    check(snap["anomaly_count"] == 1, "anomaly count")
    check(snap["analysis_count"] == 1, "analysis count")

    d.unregister_trace("t1")
    check(d.get_snapshot()["trace_count"] == 1, "trace unregistered")
    d.clear()
    check(d.get_snapshot()["trace_count"] == 0, "cleared")


# ============================================================
# 6. TraceContext
# ============================================================
async def test_trace_context() -> None:
    report_section("6. TraceContext")
    from infrastructure.service_mesh.observability import (
        TraceContext, TraceContextManager,
    )

    ctx = TraceContext()
    check(ctx.trace_id, "trace id generated")
    check(ctx.span_id, "span id generated")

    ctx.add_baggage("user", "admin")
    check(ctx.get_baggage("user") == "admin", "baggage added")
    check(ctx.remove_baggage("user"), "baggage removed")

    child = ctx.child_span_context()
    check(child.trace_id == ctx.trace_id, "child trace id")
    check(child.parent_span_id == ctx.span_id, "child parent span")

    headers = ctx.to_headers()
    check("X-Trace-Id" in headers, "trace id in headers")
    check("X-Span-Id" in headers, "span id in headers")

    parsed = TraceContext.from_headers(headers)
    check(parsed.trace_id == ctx.trace_id, "parsed trace id")
    check(parsed.span_id == ctx.span_id, "parsed span id")

    # Context manager
    TraceContextManager.clear()
    check(TraceContextManager.get_current() is None, "no current context")
    started = TraceContextManager.start_trace()
    check(TraceContextManager.get_current() is started, "current context set")
    check(TraceContextManager.get_trace_id() == started.trace_id, "trace id from manager")
    TraceContextManager.clear()


# ============================================================
# 7. SpanProcessor
# ============================================================
async def test_span_processor() -> None:
    report_section("7. SpanProcessor")
    from infrastructure.service_mesh.observability import (
        SpanProcessor, SpanKind, SpanStatus,
    )

    sp = SpanProcessor()
    span = sp.create_span("rpc_call", kind=SpanKind.RPC)
    check(span is not None, "span created")
    check(span.operation == "rpc_call", "span operation")
    check(span.status == SpanStatus.ACTIVE, "span active")

    span.set_tag("service", "oms")
    span.add_event("processing", {"step": 1})
    check(span.get_tag("service") == "oms", "tag set")

    finished = sp.finish_span(span.span_id)
    check(finished is not None, "span finished")
    check(finished.status == SpanStatus.COMPLETED, "span completed")
    check(finished.duration_s >= 0, "duration recorded")

    check(len(sp.list_active_spans()) == 0, "no active spans")
    check(len(sp.get_completed_spans()) == 1, "1 completed span")

    # Error span
    span2 = sp.create_span("db_query", kind=SpanKind.DATABASE)
    sp.finish_span(span2.span_id, error="timeout")
    check(span2.status == SpanStatus.ERROR, "span error")
    check(span2.error == "timeout", "error message")

    stats = sp.get_stats()
    check(stats["processed_count"] == 2, "processed count")

    flush_result = sp.flush()
    check(flush_result["exported"] == 2, "flushed 2 spans")


# ============================================================
# 8. TraceCollector
# ============================================================
async def test_trace_collector() -> None:
    report_section("8. TraceCollector")
    from infrastructure.service_mesh.observability import (
        TraceCollector, SpanKind,
    )

    tc = TraceCollector()
    tc.start()
    check(tc.is_running, "trace collector started")

    trace = tc.start_trace(
        operation="order_request",
        source="oms",
        destination="execution",
    )
    check(trace.trace_id, "trace id")
    check(trace.operation == "order_request", "trace operation")

    span = tc.add_span(
        trace.trace_id,
        operation="rpc",
        kind=SpanKind.RPC,
        tags={"service": "execution"},
    )
    check(span is not None, "span added")
    check(trace.span_count == 1, "span count")

    tc.finish_span(trace.trace_id, span.span_id)

    completed = tc.complete_trace(trace.trace_id, success=True)
    check(completed is not None, "trace completed")
    check(completed.duration_s >= 0, "trace duration")
    check(completed.span_count == 1, "completed span count")

    # Search traces
    tc.start_trace(operation="order_request", source="oms", destination="risk")
    results = tc.search_traces(operation="order_request")
    check(len(results) >= 1, "search results")

    timeline = tc.build_timeline(trace.trace_id)
    check(timeline is not None, "timeline built")
    check(timeline["trace_id"] == trace.trace_id, "timeline trace id")

    stats = tc.get_stats()
    check(stats["running"], "stats running")
    check(stats["trace_count"] >= 2, "trace count")
    tc.stop()


# ============================================================
# 9. MeshMetricsCollector
# ============================================================
async def test_metrics_collector() -> None:
    report_section("9. MeshMetricsCollector")
    from infrastructure.service_mesh.observability import MeshMetricsCollector

    mc = MeshMetricsCollector()
    mc.start()
    check(mc.is_running, "metrics collector started")

    mc.record_traffic("oms", 5)
    mc.record_traffic("risk", 3)
    mc.record_latency("oms", 50.0)
    mc.record_latency("oms", 100.0)
    mc.record_error("oms", "timeout")
    mc.record_retry("oms", 2)
    mc.record_connection("oms", 42)
    mc.record_policy_eval("pol-1", "allowed")

    check(mc.get_counter("mesh_traffic_total", {"service": "oms"}) == 5, "traffic counter")
    check(mc.get_counter("mesh_traffic_total", {"service": "risk"}) == 3, "risk traffic")
    check(mc.get_counter("mesh_errors_total", {"service": "oms", "type": "timeout"}) == 1, "error counter")
    check(mc.get_gauge("mesh_connections_active", {"service": "oms"}) == 42, "connection gauge")

    hist = mc.get_histogram("mesh_latency_ms", percentiles=[50, 99])
    check(hist["count"] == 2, "histogram count")
    check(hist["min"] == 50.0, "histogram min")
    check(hist["max"] == 100.0, "histogram max")
    check("p50" in hist, "p50 present")
    check("p99" in hist, "p99 present")

    prom = mc.export_prometheus()
    check("mesh_traffic_total" in prom, "prometheus has traffic")
    check("# TYPE" in prom, "prometheus has type headers")

    flush_result = mc.flush()
    check(flush_result["flushed"] > 0, "flush has points")

    stats = mc.get_stats()
    check(stats["running"], "stats running")
    check(stats["labelled_counter_count"] > 0, "labelled counter count")
    mc.stop()


# ============================================================
# 10. MetricsAggregator
# ============================================================
async def test_metrics_aggregator() -> None:
    report_section("10. MetricsAggregator")
    from infrastructure.service_mesh.observability import MetricsAggregator

    agg = MetricsAggregator(window_s=60.0, enable_ewma=True)
    agg.record("latency_ms", 50.0, service="oms", namespace="execution", cluster="c1")
    agg.record("latency_ms", 100.0, service="oms", namespace="execution", cluster="c1")
    agg.record("latency_ms", 200.0, service="risk", namespace="risk", cluster="c1")

    svc_stats = agg.get_service_metric("oms", "latency_ms")
    check(svc_stats["window"]["count"] == 2, "service window count")
    check(svc_stats["window"]["avg"] == 75.0, "service avg")
    check("ewma" in svc_stats, "service ewma present")
    check("p50" in svc_stats, "service p50 present")
    check("p99" in svc_stats, "service p99 present")

    ns_stats = agg.get_namespace_metric("execution", "latency_ms")
    check(ns_stats["window"]["count"] == 2, "namespace window count")

    cluster_stats = agg.get_cluster_metric("c1", "latency_ms")
    check(cluster_stats["window"]["count"] == 3, "cluster window count")

    global_stats = agg.get_global_metric("latency_ms")
    check(global_stats["window"]["count"] == 3, "global window count")

    overview = agg.get_overview()
    check(overview["service_count"] == 2, "service count")
    check(overview["namespace_count"] == 2, "namespace count")
    check(overview["cluster_count"] == 1, "cluster count")
    check(overview["aggregation_count"] == 3, "aggregation count")


# ============================================================
# 11. AccessLogger
# ============================================================
async def test_access_log() -> None:
    report_section("11. AccessLogger")
    from infrastructure.service_mesh.observability import AccessLogger, AccessLogEntry

    al = AccessLogger()
    al.start()
    check(al.is_running, "access logger started")

    entry = al.log_request(
        source="oms",
        destination="execution",
        method="POST",
        path="/api/orders",
        status_code=200,
        latency_ms=50.0,
        trace_id="trace-1",
        identity="spiffe://x/oms",
    )
    check(entry.source == "oms", "entry source")
    check(entry.is_success, "entry success")
    check(not entry.is_error, "entry not error")

    al.log_request(source="oms", destination="risk", status_code=500)
    check(al.get_stats()["error_count"] == 1, "error count")

    entries = al.get_entries(source="oms")
    check(len(entries) == 2, "entries by source")

    error_entries = al.get_entries(is_error=True)
    check(len(error_entries) == 1, "error entries")

    search_results = al.search("execution")
    check(len(search_results) >= 1, "search results")

    # Structured log
    struct = entry.to_structured_log()
    check("INFO" in struct, "structured log has level")

    json_str = entry.to_json()
    check('"source": "oms"' in json_str, "json has source")

    al.stop()
    check(not al.is_running, "access logger stopped")


# ============================================================
# 12. LogPipeline
# ============================================================
async def test_log_pipeline() -> None:
    report_section("12. LogPipeline")
    from infrastructure.service_mesh.observability import (
        LogPipeline, LogFilter, AccessLogger,
    )

    pipeline = LogPipeline()
    pipeline.start()
    check(pipeline.is_running, "pipeline started")

    # Add filter to only keep errors
    error_filter = LogFilter(min_status=400)
    pipeline.add_filter(error_filter)

    # Log entries
    pipeline.access_logger.log_request(
        source="oms", destination="risk",
        status_code=200, latency_ms=50.0,
    )
    pipeline.access_logger.log_request(
        source="oms", destination="risk",
        status_code=500, latency_ms=100.0,
    )

    import time as _time
    _time.sleep(0.1)  # Allow pipeline processing

    stats = pipeline.get_stats()
    check(stats["pipeline_count"] >= 1, "pipeline processed")
    check(stats["filtered_count"] >= 1, "filtered count")

    # Search storage
    results = pipeline.search("risk")
    check(len(results) >= 1, "search results")

    # Remove filter
    pipeline.remove_filter(error_filter)
    pipeline.access_logger.log_request(
        source="oms", destination="execution",
        status_code=200,
    )
    _time.sleep(0.1)

    pipeline.stop()
    check(not pipeline.is_running, "pipeline stopped")


# ============================================================
# 13. PolicyEvaluator
# ============================================================
async def test_policy_evaluator() -> None:
    report_section("13. PolicyEvaluator")
    from infrastructure.service_mesh.observability import (
        PolicyEvaluator, PolicyType, RuntimePolicy,
    )

    evaluator = PolicyEvaluator()
    evaluator.start()

    retry_policy = RuntimePolicy(
        policy_id="retry-1",
        policy_type=PolicyType.RETRY,
        config={
            "from_service": "oms",
            "to_service": "execution",
            "max_retries": 5,
            "backoff_ms": 200,
            "allowed": True,
        },
    )
    evaluator.register_policy(retry_policy)

    result = evaluator.evaluate(
        PolicyType.RETRY,
        {"source": "oms", "destination": "execution"},
    )
    check(result.allowed, "policy allowed")
    check(result.policy_id == "retry-1", "policy id matched")
    check(result.params.get("max_retries") == 5, "max_retries param")

    retry_config = evaluator.evaluate_retry({"source": "oms", "destination": "execution"})
    check(retry_config["max_retries"] == 5, "retry config")

    timeout_policy = RuntimePolicy(
        policy_id="timeout-1",
        policy_type=PolicyType.TIMEOUT,
        config={"timeout_ms": 5000, "allowed": True},
    )
    evaluator.register_policy(timeout_policy)
    timeout_config = evaluator.evaluate_timeout({"source": "oms", "destination": "execution"})
    check(timeout_config["timeout_ms"] == 5000, "timeout config")

    stats = evaluator.get_stats()
    check(stats["running"], "evaluator running")
    check(stats["evaluation_count"] >= 2, "evaluation count")

    evaluator.stop()


# ============================================================
# 14. AdaptivePolicyEngine
# ============================================================
async def test_adaptive_policy() -> None:
    report_section("14. AdaptivePolicyEngine")
    from infrastructure.service_mesh.observability import (
        AdaptivePolicyEngine, AdaptiveRule, AdjustmentSignal,
        AdjustmentAction, RuntimePolicy, RuntimePolicyRepository,
    )

    repo = RuntimePolicyRepository()
    target_policy = RuntimePolicy(
        policy_id="timeout-target",
        policy_type="timeout",
        config={"timeout_ms": 30000},
    )
    repo.add(target_policy)

    engine = AdaptivePolicyEngine(repository=repo)
    engine.start()

    # Register custom rule
    custom_rule = AdaptiveRule(
        rule_id="custom-latency",
        signal=AdjustmentSignal.LATENCY,
        threshold=3000.0,
        comparison=">",
        action=AdjustmentAction.DECREASE_TIMEOUT,
        target_policy="timeout-target",
        adjustment={"timeout_ms_delta": -5000},
    )
    engine.register_rule(custom_rule)

    # Update signal to trigger rule
    engine.update_signal(AdjustmentSignal.LATENCY, 5000.0)

    adjustments = engine.evaluate()
    check(len(adjustments) == 1, "1 adjustment")
    check(adjustments[0].action == AdjustmentAction.DECREASE_TIMEOUT, "decrease timeout action")
    check(adjustments[0].target_policy == "timeout-target", "target policy")

    # Verify policy was adjusted
    updated = repo.get("timeout-target")
    check(updated.config["timeout_ms"] == 25000, "timeout adjusted")

    # Signal below threshold - no adjustment
    engine.update_signal(AdjustmentSignal.LATENCY, 1000.0)
    adjustments2 = engine.evaluate()
    check(len(adjustments2) == 0, "0 adjustments below threshold")

    stats = engine.get_stats()
    check(stats["rule_count"] >= 1, "rule count")
    check(stats["adjustment_count"] == 1, "adjustment count")

    engine.stop()


# ============================================================
# 15. RuntimeAnalyzer
# ============================================================
async def test_runtime_analyzer() -> None:
    report_section("15. RuntimeAnalyzer")
    from infrastructure.service_mesh.observability import RuntimeAnalyzer

    analyzer = RuntimeAnalyzer()
    analyzer.start()

    # Record traffic
    for _ in range(100):
        analyzer.record_traffic("oms", "execution", 50.0, True)
    for _ in range(50):
        analyzer.record_traffic("oms", "risk", 100.0, False)
    for _ in range(200):
        analyzer.record_traffic("risk", "oms", 30.0, True)

    analyzer.record_resource("oms", cpu=0.85, memory=0.7)
    analyzer.record_resource("risk", cpu=0.5, memory=0.9)

    # Analyze traffic patterns
    result = analyzer.analyze_traffic_pattern()
    check(len(result.findings) > 0, "traffic findings")
    check(result.details["total_requests"] == 700, "total requests")

    # Analyze hot services
    hot_result = analyzer.analyze_hot_services()
    check(len(hot_result.findings) > 0, "hot service findings")

    # Analyze dependencies
    dep_result = analyzer.analyze_dependencies()
    check(len(dep_result.findings) > 0, "dependency findings")
    check(dep_result.findings[0]["dependency_count"] > 0, "has dependencies")

    # Analyze failure chains
    fail_result = analyzer.analyze_failure_chains()
    check(len(fail_result.findings) > 0, "failure chain findings")

    # Analyze resource usage
    res_result = analyzer.analyze_resource_usage()
    check(len(res_result.findings) > 0, "resource findings")

    # Analyze all
    all_results = analyzer.analyze_all()
    check(len(all_results) == 5, "5 analyses")

    stats = analyzer.get_stats()
    check(stats["analysis_count"] >= 5, "analysis count")

    analyzer.stop()


# ============================================================
# 16. AnomalyDetector
# ============================================================
async def test_anomaly_detector() -> None:
    report_section("16. AnomalyDetector")
    from infrastructure.service_mesh.observability import (
        AnomalyDetector, AnomalyType, AnomalySeverity,
    )

    detector = AnomalyDetector(
        latency_threshold_ms=100.0,
        retry_threshold=5,
        error_rate_threshold=0.3,
    )
    detector.start()

    received = []
    detector.add_listener(lambda a: received.append(a))

    # Record normal latencies
    for _ in range(15):
        detector.record_latency("oms", 50.0)
    # Spike
    anomaly = detector.record_latency("oms", 500.0)
    check(anomaly is not None, "latency anomaly detected")
    check(anomaly.anomaly_type == AnomalyType.LATENCY_SPIKE, "latency spike type")
    check(len(received) >= 1, "listener notified")

    # Retry storm
    retry_anomaly = None
    for _ in range(10):
        a = detector.record_retry("risk", 1)
        if a:
            retry_anomaly = a
    check(retry_anomaly is not None, "retry storm detected")
    check(retry_anomaly.anomaly_type == AnomalyType.RETRY_STORM, "retry storm type")

    # Error burst
    error_anomaly = None
    for _ in range(15):
        a = detector.record_error("execution", True)
        if a:
            error_anomaly = a
    check(error_anomaly is not None, "error burst detected")
    check(error_anomaly.anomaly_type == AnomalyType.ERROR_BURST, "error burst type")

    # Memory leak
    anomaly4 = None
    for usage in [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]:
        anomaly4 = detector.record_memory("cache", usage)
    check(anomaly4 is not None, "memory leak detected")
    check(anomaly4.anomaly_type == AnomalyType.MEMORY_LEAK, "memory leak type")

    anomalies = detector.get_anomalies()
    check(len(anomalies) >= 4, "4+ anomalies")

    stats = detector.get_stats()
    check(stats["detection_count"] >= 4, "detection count")
    detector.stop()


# ============================================================
# 17. SLI
# ============================================================
async def test_sli() -> None:
    report_section("17. SLI")
    from infrastructure.service_mesh.observability import (
        SLI, SLICalculator, SLIType,
    )

    sli = SLI(
        sli_id="availability-oms",
        sli_type=SLIType.AVAILABILITY,
        service="oms",
        target=0.999,
        window_s=60.0,
    )

    # Record requests
    for _ in range(100):
        sli.record_request(True)
    for _ in range(5):
        sli.record_request(False)

    result = sli.compute()
    check(result["sli_id"] == "availability-oms", "sli id")
    check(result["sample_count"] == 105, "sample count")
    check(result["value"] < 1.0, "availability < 1.0")
    check(abs(result["value"] - (100 / 105)) < 0.01, "correct availability value")

    # Latency SLI
    latency_sli = SLI(
        sli_id="latency-oms",
        sli_type=SLIType.LATENCY,
        service="oms",
        target=100.0,
    )
    for lat in [10, 20, 30, 40, 50, 200]:
        latency_sli.record_request(True, lat)
    lat_result = latency_sli.compute()
    check(lat_result["value"] >= 100, "p99 latency >= 100")

    # SLI Calculator
    calc = SLICalculator()
    calc.register_sli(sli)
    calc.register_sli(latency_sli)
    check(len(calc.list_slis()) == 2, "2 SLIs registered")

    calc.record_request("oms", True, 50.0)
    results = calc.compute_all()
    check(len(results) == 2, "2 SLI results")

    calc.start()
    check(calc.is_running, "calculator started")
    calc.stop()


# ============================================================
# 18. SLO
# ============================================================
async def test_slo() -> None:
    report_section("18. SLO")
    from infrastructure.service_mesh.observability import (
        SLO, SLOMonitor, SLIType, SLOStatus,
    )

    monitor = SLOMonitor()
    monitor.start()

    slo = SLO(
        slo_id="availability-slo",
        name="OMS Availability",
        service="oms",
        sli_type=SLIType.AVAILABILITY,
        target=0.95,
        window_days=30,
    )
    monitor.register_slo(slo)
    check(len(monitor.list_slos()) == 1, "1 SLO registered")

    # Record mostly successful requests
    for _ in range(100):
        monitor.record_request("oms", True, 50.0)
    for _ in range(2):
        monitor.record_request("oms", False, 50.0)

    result = slo.evaluate()
    check(result["status"] == SLOStatus.OK, "SLO ok")
    check(result["current_value"] > 0.95, "availability > 0.95")

    # Violate SLO
    for _ in range(20):
        monitor.record_request("oms", False, 50.0)

    result2 = slo.evaluate()
    check(result2["status"] == SLOStatus.VIOLATED, "SLO violated")

    violations = slo.get_violations()
    check(len(violations) >= 1, "violations recorded")

    # Evaluate all
    all_results = monitor.evaluate_all()
    check(len(all_results) == 1, "1 SLO evaluated")

    stats = monitor.get_stats()
    check(stats["slo_count"] == 1, "slo count")
    check(stats["violation_count"] >= 1, "violation count")

    monitor.stop()


# ============================================================
# 19. DashboardProvider
# ============================================================
async def test_dashboard() -> None:
    report_section("19. DashboardProvider")
    from infrastructure.service_mesh.observability import (
        DashboardProvider, DashboardView, TraceCollector,
        MeshMetricsCollector, AccessLogger, SLOMonitor,
        AnomalyDetector, RuntimeAnalyzer,
    )

    dashboard = DashboardProvider()
    dashboard.register_data_source("trace_collector", TraceCollector())
    dashboard.register_data_source("metrics_collector", MeshMetricsCollector())
    dashboard.register_data_source("access_logger", AccessLogger())
    dashboard.register_data_source("slo_monitor", SLOMonitor())
    dashboard.register_data_source("anomaly_detector", AnomalyDetector())
    dashboard.register_data_source("runtime_analyzer", RuntimeAnalyzer())
    dashboard.start()

    overview = dashboard.get_overview()
    check(overview["view"] == "overview", "overview view")
    check("mesh" in overview, "mesh in overview")

    topology = dashboard.get_topology()
    check(topology["view"] == "topology", "topology view")
    check("nodes" in topology, "nodes in topology")

    traces = dashboard.get_traces(limit=5)
    check(traces["view"] == "trace", "trace view")

    slo_view = dashboard.get_slo()
    check(slo_view["view"] == "slo", "slo view")

    anomalies = dashboard.get_anomalies()
    check(anomalies["view"] == "anomaly", "anomaly view")

    analysis = dashboard.get_analysis()
    check(analysis["view"] == "analysis", "analysis view")

    # Generic get_view
    health_view = dashboard.get_view(DashboardView.HEALTH)
    check("view" in health_view, "health view via get_view")

    stats = dashboard.get_stats()
    check(stats["running"], "dashboard running")
    check(stats["request_count"] >= 6, "request count")
    dashboard.stop()


# ============================================================
# 20. ObservabilityAPI
# ============================================================
async def test_api() -> None:
    report_section("20. ObservabilityAPI")
    from infrastructure.service_mesh.observability import ObservabilityAPI

    api = ObservabilityAPI()
    api.start()

    routes = api.list_routes()
    check(len(routes) >= 10, "10+ routes registered")

    # Test overview
    resp = api.handle("GET", "/mesh/overview")
    check(resp.status == 200, "overview 200")
    check("data" in resp.to_dict(), "overview has data")

    # Test traces
    resp2 = api.handle("GET", "/mesh/traces", {"limit": 10})
    check(resp2.status == 200, "traces 200")

    # Test SLO
    resp3 = api.handle("GET", "/mesh/slo")
    check(resp3.status == 200, "slo 200")

    # Test 404
    resp4 = api.handle("GET", "/unknown/path")
    check(resp4.status == 404, "unknown 404")

    stats = api.get_stats()
    check(stats["running"], "api running")
    check(stats["request_count"] >= 3, "request count")
    api.stop()


# ============================================================
# 21. ObservabilityScheduler
# ============================================================
async def test_scheduler() -> None:
    report_section("21. ObservabilityScheduler")
    from infrastructure.service_mesh.observability import ObservabilityScheduler

    scheduler = ObservabilityScheduler()
    check(not scheduler.is_running, "not running")

    call_count = 0

    def test_task():
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    scheduler.register_task("test-task", test_task, interval_s=0.1, enabled=True)
    check(len(scheduler.get_stats()["tasks"]) >= 6, "tasks registered")

    await scheduler.start()
    check(scheduler.is_running, "scheduler running")
    await asyncio.sleep(0.5)
    await scheduler.stop()
    check(not scheduler.is_running, "scheduler stopped")

    status = scheduler.get_task_status("test-task")
    check(status["run_count"] >= 1, "task ran at least once")

    check(scheduler.disable_task("test-task"), "task disabled")
    check(scheduler.enable_task("test-task"), "task enabled")
    check(scheduler.unregister_task("test-task"), "task unregistered")


# ============================================================
# 22. MeshObservability (Orchestration)
# ============================================================
async def test_observability_manager() -> None:
    report_section("22. MeshObservability")
    from infrastructure.service_mesh.observability import (
        MeshObservability, RuntimePolicy, PolicyType,
        SLO, SLIType,
    )

    obs = MeshObservability()
    check(not obs.is_running, "not running initially")

    result = await obs.initialize()
    check(result["success"], "initialized")
    check(obs.is_running, "running after init")

    # Start trace
    trace = obs.start_trace(
        operation="test_request",
        source="oms",
        destination="execution",
    )
    check(trace.trace_id, "trace started")

    # Record access
    entry = obs.record_access(
        source="oms",
        destination="execution",
        method="POST",
        path="/api/orders",
        status_code=200,
        latency_ms=50.0,
        trace_id=trace.trace_id,
    )
    check(entry.source == "oms", "access recorded")

    # Complete trace
    obs.complete_trace(trace.trace_id, success=True)

    # Register policy
    policy = RuntimePolicy(
        policy_id="test-retry",
        policy_type=PolicyType.RETRY,
        config={"max_retries": 3, "allowed": True},
    )
    obs.register_policy(policy)

    # Register SLO
    slo = SLO(
        slo_id="test-slo",
        service="oms",
        sli_type=SLIType.AVAILABILITY,
        target=0.99,
    )
    obs.register_slo(slo)

    # Update signals for adaptive
    obs.update_signals({"latency": 6000.0})

    # Analyze runtime
    analyses = obs.analyze_runtime()
    check(len(analyses) == 5, "5 analyses")

    # Health check
    health = await obs.health_check()
    check("components" in health, "health has components")

    # Stats
    stats = obs.get_stats()
    check(stats["started"], "stats started")
    check("trace" in stats, "stats has trace")
    check("metrics_collector" in stats, "stats has metrics_collector")
    check("access_logger" in stats, "stats has access_logger")
    check("policy_evaluator" in stats, "stats has policy_evaluator")
    check("slo_monitor" in stats, "stats has slo_monitor")

    # Shutdown
    shutdown = await obs.shutdown()
    check(shutdown["success"], "shutdown success")
    check(not obs.is_running, "not running after shutdown")


# ============================================================
# 23. ServiceMesh Observability Integration
# ============================================================
async def test_mesh_observability_integration() -> None:
    report_section("23. ServiceMesh Observability Integration")
    from infrastructure.service_mesh import ServiceMesh
    from infrastructure.service_mesh.observability import MeshObservability

    mesh = ServiceMesh(mesh_id="observability-test-mesh")
    check(isinstance(mesh.observability, MeshObservability), "observability property")

    result = await mesh.startup(timeout_s=30.0)
    check(result.get("bootstrapped"), "mesh bootstrapped")
    check(mesh.is_running, "mesh running")
    check(mesh.observability.is_running, "observability running")

    stats = mesh.get_stats()
    check("observability" in stats, "observability in stats")
    check(stats["observability"]["started"], "observability stats started")

    health = await mesh.health_check()
    check("observability" in health["components"], "observability in health")

    shutdown = await mesh.shutdown()
    check(shutdown["success"], "mesh shutdown")
    check(not mesh.observability.is_running, "observability stopped")


# ============================================================
# Main
# ============================================================
async def main() -> None:
    global FAILED
    print("=" * 60)
    print("ICYQuant Service Mesh Observability - Validation Suite")
    print("=" * 60)

    tests = [
        test_events,
        test_metrics,
        test_telemetry,
        test_health,
        test_diagnostics,
        test_trace_context,
        test_span_processor,
        test_trace_collector,
        test_metrics_collector,
        test_metrics_aggregator,
        test_access_log,
        test_log_pipeline,
        test_policy_evaluator,
        test_adaptive_policy,
        test_runtime_analyzer,
        test_anomaly_detector,
        test_sli,
        test_slo,
        test_dashboard,
        test_api,
        test_scheduler,
        test_observability_manager,
        test_mesh_observability_integration,
    ]

    for test in tests:
        try:
            await test()
        except Exception:
            FAILED += 1
            FAILURES.append(
                f"  - EXCEPTION in {test.__name__}: {traceback.format_exc()}"
            )

    print("\n" + "=" * 60)
    print(f"Results: {PASSED} passed, {FAILED} failed")
    if FAILURES:
        print("\nFailures:")
        for failure in FAILURES:
            print(failure)
    print("=" * 60)

    return FAILED


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
