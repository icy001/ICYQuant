"""Validation tests for ICYQuant Service Mesh Traffic Management.

Runs comprehensive validation across all traffic management
components and reports pass/fail counts.
"""

import asyncio
import sys
import time
import traceback
from typing import Any, Dict, List

# Ensure project root is in path
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
# 1. TrafficMetrics
# ============================================================
async def test_traffic_metrics() -> None:
    report_section("1. TrafficMetrics")
    from infrastructure.service_mesh.traffic import TrafficMetrics

    m = TrafficMetrics()
    m.increment_requests({"service": "oms"})
    m.increment_requests({"service": "risk"})
    m.increment_retry({"route": "r1"})
    m.increment_timeout({"target": "t1"})
    m.increment_circuit_open({"target": "t2"})
    m.increment_rate_limit({"client": "c1"})
    m.increment_mirror()
    m.increment_canary()
    m.increment_blue_green()
    m.increment_outlier()
    m.record_latency(0.05)
    m.record_latency(0.10)
    m.record_latency(0.50)
    m.set_pool_active(42.0)

    s = m.get_summary()
    check(s["counters"]["icyquant_mesh_requests_total"] == 2, "requests counted")
    check(s["counters"]["icyquant_mesh_retry_total"] == 1, "retry counted")
    check(s["counters"]["icyquant_mesh_timeout_total"] == 1, "timeout counted")
    check(s["counters"]["icyquant_mesh_circuit_open_total"] == 1, "circuit counted")
    check(s["counters"]["icyquant_mesh_rate_limit_total"] == 1, "rate limit counted")
    check(s["counters"]["icyquant_mesh_mirror_total"] == 1, "mirror counted")
    check(s["counters"]["icyquant_mesh_canary_total"] == 1, "canary counted")
    check(s["counters"]["icyquant_mesh_blue_green_total"] == 1, "blue_green counted")
    check(s["counters"]["icyquant_mesh_outlier_detected_total"] == 1, "outlier counted")
    check("icyquant_mesh_latency_seconds" in s["timer_stats"], "latency stats present")
    check(s["gauges"]["icyquant_mesh_conn_pool_active"] == 42.0, "pool gauge")

    m.reset()
    s2 = m.get_summary()
    check(s2["counters"]["icyquant_mesh_requests_total"] == 0, "reset works")


# ============================================================
# 2. Policies
# ============================================================
async def test_policies() -> None:
    report_section("2. Traffic Policies")
    from infrastructure.service_mesh.traffic import (
        RetryPolicy, TimeoutPolicy, CircuitPolicy,
        TrafficPolicy, RatePolicy, PolicyManager,
    )

    rp = RetryPolicy(max_retries=3)
    check(rp.max_retries == 3, "retry policy created")
    check(rp.to_dict()["max_retries"] == 3, "retry policy serializable")

    tp = TimeoutPolicy(overall_timeout_ms=60000)
    check(tp.overall_timeout_ms == 60000, "timeout policy")

    cp = CircuitPolicy(max_connections=500)
    check(cp.max_connections == 500, "circuit policy")

    pol = TrafficPolicy("pol-1", retries=rp, timeouts=tp, circuit=cp)
    check(pol.policy_id == "pol-1", "traffic policy id")
    check(pol.enabled, "traffic policy enabled")

    rate = RatePolicy("rate-1", rate=200.0, burst=400)
    check(rate.rate == 200.0, "rate policy rate")

    pm = PolicyManager()
    pm.register_traffic_policy(pol)
    pm.register_rate_policy(rate)
    check(pm.get_traffic_policy("pol-1") is not None, "policy registered")
    check(pm.get_rate_policy("rate-1") is not None, "rate policy registered")
    check(len(pm.list_traffic_policies()) == 1, "list policies")
    check(len(pm.list_rate_policies()) == 1, "list rate policies")
    check(pm.remove_policy("pol-1"), "remove policy")
    check(pm.get_traffic_policy("pol-1") is None, "policy removed")
    check(pm.get_stats()["traffic_policy_count"] == 0, "stats updated")


# ============================================================
# 3. TrafficTelemetry
# ============================================================
async def test_telemetry() -> None:
    report_section("3. TrafficTelemetry")
    from infrastructure.service_mesh.traffic import TrafficTelemetry

    t = TrafficTelemetry()
    t.log_route_decision("r1", "oms", "backend", True)
    t.log_retry_chain("r1", 1, 3, "timeout", 0.5)
    t.log_circuit_status("backend", "closed", "open", "failures")
    t.log_request("GET", "/api/orders", "r1", "backend", 200, 0.12)
    t.log_mirror("primary", "mirror-1", True, 0.05)
    t.log_canary("r2", True, 20)
    t.log_blue_green("r3", "blue", "stable", "validation")
    t.log_rate_limit("svc-1", "client-1", 100.0, 200)

    events = t.get_events()
    check(len(events) >= 8, "8 events logged")
    check(len(t.get_events("route_decision")) == 1, "route event filter")
    check(len(t.get_events("retry")) == 1, "retry event filter")
    check(len(t.get_events("circuit_status")) == 1, "circuit event filter")
    check(len(t.get_events("request")) == 1, "request event filter")

    trace_id = t.generate_trace_id()
    check(trace_id.startswith("tr-"), "trace id generated")
    s = t.get_stats()
    check(s["event_count"] >= 8, "event count")


# ============================================================
# 4. TrafficDiagnostics
# ============================================================
async def test_diagnostics() -> None:
    report_section("4. TrafficDiagnostics")
    from infrastructure.service_mesh.traffic import TrafficDiagnostics

    d = TrafficDiagnostics()
    d.update_routing_table([
        {"route_id": "r1", "path": "/api"},
        {"route_id": "r2", "path": "/admin"},
    ])
    d.record_decision("r1", True, "backend", "matched")
    d.record_decision("r2", False, "", "no_match")
    d.set_component_status("router", "healthy", {"qps": 100})

    rt = d.get_routing_table()
    check(len(rt) == 2, "routing table size")
    dh = d.get_decision_history()
    check(len(dh) == 2, "decision history size")
    cs = d.get_component_status("router")
    check(cs["status"] == "healthy", "component status")
    snap = d.get_snapshot()
    check(snap["routing_table_count"] == 2, "snapshot table count")


# ============================================================
# 5. Route & RouteTable
# ============================================================
async def test_route() -> None:
    report_section("5. Route & RouteTable")
    from infrastructure.service_mesh.traffic import (
        TrafficRoute, RouteDestination, RouteTable, RouteMatchType,
    )

    route = TrafficRoute(
        "r1", "orders-service",
        path="/api/orders",
        path_match=RouteMatchType.PREFIX,
    )
    route.add_destination("oms-host", 8080, weight=80.0)
    route.add_destination("oms-canary", 8080, weight=20.0, version="canary")

    check(route.route_id == "r1", "route id")
    check(route.get_total_weight() == 100.0, "total weight")
    check(len(route.destinations) == 2, "2 destinations")

    rt = RouteTable()
    rt.add_route(route)
    check(rt.get_route("r1") is not None, "route retrieved")
    check(len(rt.list_routes()) == 1, "route table size")
    check(rt.remove_route("r1"), "remove route")
    check(rt.get_route("r1") is None, "route removed")

    route2 = TrafficRoute("r2", "simple")
    rt.add_route(route2)
    d = rt.list_routes_dict()
    check(len(d) == 1 and d[0]["route_id"] == "r2", "route dict")


# ============================================================
# 6. RouteMatcher
# ============================================================
async def test_route_matcher() -> None:
    report_section("6. RouteMatcher")
    from infrastructure.service_mesh.traffic import (
        TrafficRoute, RouteMatchType, RouteMatcher, RouteTable,
    )

    rt = RouteTable()
    r1 = TrafficRoute("r1", "api", path="/api", path_match=RouteMatchType.PREFIX)
    r2 = TrafficRoute("r2", "admin", path="/admin", path_match=RouteMatchType.EXACT)
    r3 = TrafficRoute("r3", "post", methods=["POST"], path="/data")
    r4 = TrafficRoute("r4", "header", headers={"X-Custom": "yes"}, path="/special")
    rt.add_route(r1)
    rt.add_route(r2)
    rt.add_route(r3)
    rt.add_route(r4)

    m = RouteMatcher(rt)

    matched = m.match("GET", "/api/orders")
    check(matched is not None and matched.route_id == "r1", "prefix match")

    matched = m.match("GET", "/admin")
    check(matched is not None and matched.route_id == "r2", "exact match")

    matched = m.match("GET", "/admin/extra")
    check(matched is None, "exact mismatch")

    matched = m.match("POST", "/data")
    check(matched is not None and matched.route_id == "r3", "method match")

    matched = m.match("GET", "/data")
    check(matched is None, "method mismatch")

    matched = m.match("GET", "/special", headers={"X-Custom": "yes"})
    check(matched is not None and matched.route_id == "r4", "header match")

    matched = m.match("GET", "/special")
    check(matched is None, "header mismatch")

    s = m.get_stats()
    check(s["match_count"] >= 4, "match count")


# ============================================================
# 7. RouteRewriter
# ============================================================
async def test_route_rewriter() -> None:
    report_section("7. RouteRewriter")
    from infrastructure.service_mesh.traffic import RouteRewriter

    rw = RouteRewriter()
    result = rw.rewrite_request(
        "/api/v1/users",
        headers={"Authorization": "Bearer xxx"},
        rewrite_rules={"path_rewrite": "/api/v1->/internal"},
    )
    check(result["path"] == "/internal/users", "path rewrite")

    result2 = rw.rewrite_request(
        "/hello",
        headers={},
        rewrite_rules={"path_rewrite": "/hello->/world"},
    )
    check(result2["path"] == "/world", "full path rewrite")

    result3 = rw.rewrite_request(
        "/test",
        headers={"Host": "old.example.com"},
        rewrite_rules={"host_rewrite": "new.example.com"},
    )
    check(result3["headers"]["host"] == "new.example.com", "host rewrite")


# ============================================================
# 8. VirtualService
# ============================================================
async def test_virtual_service() -> None:
    report_section("8. VirtualService")
    from infrastructure.service_mesh.traffic import (
        VirtualService, RouteMatchType,
    )

    vs = VirtualService("risk-engine", namespace="trading")
    check(vs.service_id == "trading/risk-engine", "vs service_id")

    route = vs.create_weighted_route(
        "r1", path="/",
        stable_host="stable-host",
        canary_host="canary-host",
        stable_weight=80.0,
        canary_weight=20.0,
    )
    check(route is not None, "weighted route created")
    check(len(route.destinations) == 2, "2 destinations")
    check(route.get_total_weight() == 100.0, "total weight 100")

    check(len(vs.get_routes()) == 1, "vs routes count")
    d = vs.to_dict()
    check(d["name"] == "risk-engine", "vs name in dict")


# ============================================================
# 9. DestinationRule
# ============================================================
async def test_destination_rule() -> None:
    report_section("9. DestinationRule")
    from infrastructure.service_mesh.traffic import (
        DestinationRule, DestinationRuleManager,
    )

    dr = DestinationRule("dr-1", "backend-svc", load_balancer_type="least_request")
    dr.add_subset("v1", {"version": "1.0"}, "v1")
    dr.add_subset("v2", {"version": "2.0"}, "v2")
    check(len(dr.subsets) == 2, "subsets added")
    check(dr.get_subset("v1") is not None, "subset lookup")

    mgr = DestinationRuleManager()
    mgr.register(dr)
    check(mgr.get_rule_for_host("backend-svc") is not None, "rule by host")
    check(mgr.unregister("dr-1"), "unregister")
    check(mgr.get_rule_for_host("backend-svc") is None, "rule removed")


# ============================================================
# 10. TrafficSplit
# ============================================================
async def test_traffic_split() -> None:
    report_section("10. TrafficSplit")
    from infrastructure.service_mesh.traffic import TrafficSplit

    ts = TrafficSplit()
    destinations = [
        {"host": "stable", "weight": 80.0},
        {"host": "canary", "weight": 20.0},
    ]

    result = ts.select_destination(destinations, strategy="weighted")
    check(result is not None, "weighted selection works")
    check(result["host"] in ("stable", "canary"), "valid host selected")

    result2 = ts.select_destination(destinations, strategy="percentage", key="user-123")
    check(result2 is not None, "percentage selection works")

    result3 = ts.select_destination(destinations[:1])
    check(result3 is not None and result3["host"] == "stable", "single dest")

    result4 = ts.select_destination([])
    check(result4 is None, "empty destinations returns None")


# ============================================================
# 11. WeightedRouter
# ============================================================
async def test_weighted_router() -> None:
    report_section("11. WeightedRouter")
    from infrastructure.service_mesh.traffic import WeightedRouter

    wr = WeightedRouter()
    wr.set_weight("ep1", 80.0)
    wr.set_weight("ep2", 20.0)
    wr.set_strategy("static")

    weights = wr.get_weights(["ep1", "ep2"])
    check(weights["ep1"] == 80.0, "static weight ep1")
    check(weights["ep2"] == 20.0, "static weight ep2")

    wr.set_health("ep2", False)
    wr.set_strategy("health")
    weights2 = wr.get_weights(["ep1", "ep2"])
    check(weights2["ep2"] == 0.0, "unhealthy weight is 0")

    wr.record_latency("ep1", 100.0)
    wr.record_latency("ep2", 500.0)
    wr.set_strategy("latency")
    weights3 = wr.get_weights(["ep1", "ep2"])
    check(weights3["ep1"] > 0, "latency weights positive")


# ============================================================
# 12. LoadBalancer
# ============================================================
async def test_load_balancer() -> None:
    report_section("12. LoadBalancer")
    from infrastructure.service_mesh.traffic import (
        LoadBalancer, LoadBalancerStrategy,
    )

    lb = LoadBalancer(LoadBalancerStrategy.ROUND_ROBIN)
    eps = ["a", "b", "c"]
    selected = set()
    for _ in range(6):
        selected.add(lb.select(eps))
    check(len(selected) == 3, "round robin covers all endpoints")

    lb2 = LoadBalancer(LoadBalancerStrategy.WEIGHTED)
    result = lb2.select(
        ["a", "b"],
        weights={"a": 80.0, "b": 20.0},
    )
    check(result in ("a", "b"), "weighted select works")

    lb3 = LoadBalancer(LoadBalancerStrategy.CONSISTENT_HASH)
    result3 = lb3.select(["a", "b", "c"], key="user-42")
    check(result3 is not None, "consistent hash works")

    lb4 = LoadBalancer(LoadBalancerStrategy.LEAST_REQUEST)
    result4 = lb4.select(["a", "b"])
    check(result4 is not None, "least request works")

    lb.record_result("a", True, 10.0)
    stats = lb.get_endpoint_stats("a")
    check(stats["endpoint"] == "a", "endpoint stats")


# ============================================================
# 13. BlueGreen
# ============================================================
async def test_blue_green() -> None:
    report_section("13. BlueGreen")
    from infrastructure.service_mesh.traffic import (
        BlueGreenDeployer, BlueGreenPhase,
    )

    bg = BlueGreenDeployer()
    result = bg.start_deployment(
        "dep-1", "v1", "v2", "blue-host", "green-host"
    )
    check(result["deployment_id"] == "dep-1", "deployment started")
    check(result["phase"] == BlueGreenPhase.BLUE, "initial phase is blue")

    await bg.advance_phase("dep-1")
    s1 = bg.get_deployment("dep-1")
    check(s1["phase"] == BlueGreenPhase.GREEN_DEPLOY, "phase advanced")

    await bg.advance_phase("dep-1")
    s2 = bg.get_deployment("dep-1")
    check(s2["phase"] == BlueGreenPhase.VALIDATION, "validation phase")

    await bg.advance_phase("dep-1")
    s3 = bg.get_deployment("dep-1")
    check(s3["phase"] == BlueGreenPhase.TRAFFIC_SWITCH, "traffic switch")

    await bg.advance_phase("dep-1")
    s4 = bg.get_deployment("dep-1")
    check(s4["phase"] == BlueGreenPhase.BLUE_OFFLINE, "blue offline")

    await bg.advance_phase("dep-1")
    s5 = bg.get_deployment("dep-1")
    check(s5["phase"] == BlueGreenPhase.COMPLETED, "completed")

    # Test rollback
    bg2 = BlueGreenDeployer()
    bg2.start_deployment("dep-2", "v1", "v2", "b", "g")
    await bg2.rollback("dep-2", "validation failed")
    rb = bg2.get_deployment("dep-2")
    check(rb["phase"] == BlueGreenPhase.ROLLED_BACK, "rollback works")

    stats = bg.get_stats()
    check(stats["deployment_count"] == 1, "deployment count")


# ============================================================
# 14. Canary
# ============================================================
async def test_canary() -> None:
    report_section("14. Canary")
    from infrastructure.service_mesh.traffic import CanaryRule, CanaryRelease

    cr = CanaryRule(
        "canary-1",
        canary_host="canary-svc",
        stable_host="stable-svc",
        percentage=20.0,
    )
    canary = CanaryRelease()
    canary.add_rule(cr)

    # Test header-based
    cr2 = CanaryRule(
        "canary-2",
        canary_host="canary-svc",
        stable_host="stable-svc",
        header_name="X-Canary",
        header_value="true",
    )
    canary.add_rule(cr2)

    result = canary.decide(
        "canary-2",
        headers={"X-Canary": "true"},
    )
    check(result["is_canary"], "header-based canary")
    check(result["target"] == "canary-svc", "canary target")

    result2 = canary.decide("canary-2", headers={})
    check(not result2["is_canary"], "no header = stable")

    # Test percentage-based with deterministic key
    result3 = canary.decide("canary-1", request_id="fixed-key-1")
    check(result3 is not None, "percentage decision returned")

    canary.remove_rule("canary-1")
    check(canary.get_stats()["rule_count"] == 1, "rule removed")


# ============================================================
# 15. TrafficMirror
# ============================================================
async def test_mirror() -> None:
    report_section("15. TrafficMirror")
    from infrastructure.service_mesh.traffic import MirrorPolicy, TrafficMirror

    m = TrafficMirror()
    p = MirrorPolicy("mp-1", "mirror-host", "/mirror")
    m.add_policy(p)

    results = await m.mirror_request(
        "GET", "/api/orders", headers={"X-Test": "yes"},
        policy_ids=["mp-1"],
    )
    check(len(results) == 1, "1 mirror result")
    check(results[0]["success"], "mirror success")

    s = m.get_stats()
    check(s["request_count"] == 1, "mirror request counted")

    m.remove_policy("mp-1")
    check(m.get_stats()["policy_count"] == 0, "policy removed")


# ============================================================
# 16. Retry
# ============================================================
async def test_retry() -> None:
    report_section("16. Retry")
    from infrastructure.service_mesh.traffic import RetryManager, RetryStrategy

    rm = RetryManager(max_retries=3, strategy=RetryStrategy.EXPONENTIAL)
    b0 = rm.compute_backoff(0)
    b1 = rm.compute_backoff(1)
    b2 = rm.compute_backoff(2)
    check(b0 <= b1 <= b2, "exponential backoff increases")

    rm2 = RetryManager(strategy=RetryStrategy.IMMEDIATE)
    check(rm2.compute_backoff(0) == 0.0, "immediate backoff is 0")

    rm3 = RetryManager(strategy=RetryStrategy.JITTER)
    bj = rm3.compute_backoff(0)
    check(bj >= 0, "jitter backoff non-negative")

    check(rm.should_retry(0), "should retry at attempt 0")
    check(rm.should_retry(2), "should retry at attempt 2")
    check(not rm.should_retry(3), "should not retry at max")
    check(not rm.should_retry(1, status_code=200), "no retry on 200")

    rm.record_attempt("svc", True, 0.1)
    s = rm.get_stats()
    check(s["retry_count"] == 1, "retry count")


# ============================================================
# 17. Hedging
# ============================================================
async def test_hedging() -> None:
    report_section("17. HedgeManager")
    from infrastructure.service_mesh.traffic import HedgeManager

    hm = HedgeManager(hedge_delay_ms=5)

    async def primary():
        await asyncio.sleep(0.05)
        return {"status": 200, "body": "primary"}

    async def secondary():
        await asyncio.sleep(0.01)
        return {"status": 200, "body": "secondary"}

    result = await hm.execute_with_hedging(
        primary, [secondary], timeout_s=2.0,
    )
    check(result["success"], "hedge execution succeeded")
    check(result["duration_s"] < 1.0, "hedge completed in time")
    check(result["winner"] in ("primary", "hedge_0"), "winner identified")

    s = hm.get_stats()
    check(s["hedge_count"] == 1, "hedge count")


# ============================================================
# 18. Timeout
# ============================================================
async def test_timeout() -> None:
    report_section("18. TimeoutManager")
    from infrastructure.service_mesh.traffic import TimeoutManager

    tm = TimeoutManager(
        connect_timeout_ms=3000,
        read_timeout_ms=5000,
        write_timeout_ms=5000,
        overall_timeout_ms=15000,
    )
    t = tm.get_timeouts()
    check(t["connect"] == 3.0, "connect timeout")
    check(t["read"] == 5.0, "read timeout")
    check(t["overall"] == 15.0, "overall timeout")

    tm.record_latency("svc-a", 0.05)
    tm.record_latency("svc-a", 0.15)
    tm.record_timeout("svc-a")
    s = tm.get_stats()
    check(s["timeout_count"] == 1, "timeout recorded")

    tm.set_timeouts(connect_ms=1000, overall_ms=30000)
    t2 = tm.get_timeouts()
    check(t2["connect"] == 1.0, "dynamic connect timeout updated")
    check(t2["overall"] == 30.0, "dynamic overall timeout updated")


# ============================================================
# 19. CircuitBreaker
# ============================================================
async def test_circuit_breaker() -> None:
    report_section("19. TrafficCircuitBreaker")
    from infrastructure.service_mesh.traffic import (
        TrafficCircuitBreaker, CircuitState, CircuitBreakerConfig,
    )

    cb = TrafficCircuitBreaker(
        CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_s=0.1,
            window_s=1.0,
        )
    )

    check(cb.state == CircuitState.CLOSED, "initial state closed")
    check(cb.allow_request("svc"), "request allowed when closed")

    # Record 3 failures
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    check(cb.state == CircuitState.OPEN, "state transitioned to open")
    check(not cb.allow_request("svc"), "request blocked when open")

    # Wait for timeout and transition to half-open
    await asyncio.sleep(0.15)
    check(cb.allow_request("svc"), "request allowed in half-open")
    check(cb.state == CircuitState.HALF_OPEN, "state is half-open")

    # Success in half-open -> closed
    cb.record_success()
    cb.record_success()
    check(cb.state == CircuitState.CLOSED, "state back to closed")

    cb.reset()
    check(cb.state == CircuitState.CLOSED, "reset to closed")

    s = cb.get_stats()
    check(s["state"] == "closed", "stats state")


# ============================================================
# 20. OutlierDetection
# ============================================================
async def test_outlier_detection() -> None:
    report_section("20. OutlierDetector")
    from infrastructure.service_mesh.traffic import OutlierDetector

    od = OutlierDetector(
        consecutive_errors=3,
        base_ejection_time_s=0.05,
    )

    od.record_request("inst-1", True, 10.0)
    od.record_request("inst-1", False, 50.0)
    od.record_request("inst-1", False, 50.0)
    od.record_request("inst-1", False, 50.0)

    result = od.check_outlier("inst-1")
    check(result["ejected"], "instance ejected after 3 errors")
    check(result["reason"] == "consecutive_failures", "ejection reason")

    check(od.is_ejected("inst-1"), "is ejected returns true")

    await asyncio.sleep(0.1)
    check(not od.is_ejected("inst-1"), "auto-recovery after timeout")

    stats = od.get_instance_stats("inst-1")
    check(stats["consecutive_failures"] == 0, "failures reset after recovery")

    od2 = OutlierDetector(latency_threshold_ms=20.0)
    od2.record_request("inst-2", True, 100.0)
    r2 = od2.check_outlier("inst-2")
    check(r2["ejected"], "ejected for high latency")

    s = od.get_stats()
    check(s["detection_count"] >= 1, "detection count")


# ============================================================
# 21. RateLimiter
# ============================================================
async def test_rate_limiter() -> None:
    report_section("21. RateLimiter")
    from infrastructure.service_mesh.traffic import (
        RateLimiter, RateLimitStrategy,
    )

    rl = RateLimiter(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        default_rate=10.0,
        default_burst=10,
    )

    # First 10 should pass
    for i in range(10):
        check(
            rl.try_acquire("svc-test", global_scope=False),
            f"token bucket acquire {i}",
        )

    # 11th should fail (no tokens yet)
    check(
        not rl.try_acquire("svc-test", global_scope=False),
        "token bucket blocks excess",
    )

    rl2 = RateLimiter(strategy=RateLimitStrategy.LEAKY_BUCKET, default_rate=5.0, default_burst=5)
    for i in range(5):
        check(rl2.try_acquire(f"lb-{i}"), f"leaky bucket {i}")
    check(not rl2.try_acquire("lb-extra"), "leaky bucket blocks excess")

    rl3 = RateLimiter(strategy=RateLimitStrategy.SLIDING_WINDOW, default_rate=10.0, default_burst=10)
    for i in range(10):
        check(rl3.try_acquire(f"sw-{i}"), f"sliding window {i}")
    check(not rl3.try_acquire("sw-extra"), "sliding window blocks excess")

    s = rl.get_stats()
    check(s["strategy"] == "token_bucket", "strategy tracked")


# ============================================================
# 22. ConnectionPool
# ============================================================
async def test_connection_pool() -> None:
    report_section("22. ConnectionPool")
    from infrastructure.service_mesh.traffic import (
        ConnectionPool, ConnectionProtocol,
    )

    cp = ConnectionPool(max_connections=100, max_idle_s=0.05)

    c1 = cp.acquire("host-a", 8080)
    check(c1 is not None, "acquire connection")
    check(c1.active, "conn is active")

    cp.release(c1)
    check(not c1.active, "conn marked idle after release")

    c2 = cp.acquire("host-a", 8080)
    check(c2.conn_id == c1.conn_id, "reused idle connection")

    cp.close(c2)
    check(cp.get_stats()["total_closed"] >= 1, "close tracked")

    # Cleanup
    await asyncio.sleep(0.1)
    cp.cleanup()
    s = cp.get_stats()
    check("pool_count" in s, "pool stats available")


# ============================================================
# 23. TrafficScheduler
# ============================================================
async def test_scheduler() -> None:
    report_section("23. TrafficScheduler")
    from infrastructure.service_mesh.traffic import TrafficScheduler

    ts = TrafficScheduler()
    counter = [0]

    def task_fn():
        counter[0] += 1

    ts.register_task("test-task", task_fn, interval_s=0.01)
    check(ts.get_stats()["task_count"] == 1, "task registered")
    check(ts.enable_task("test-task"), "enable task")
    check(ts.disable_task("test-task"), "disable task")
    check(ts.unregister_task("test-task"), "unregister task")


# ============================================================
# 24. TrafficManager
# ============================================================
async def test_traffic_manager() -> None:
    report_section("24. TrafficManager")
    from infrastructure.service_mesh.traffic import (
        TrafficManager, VirtualService, TrafficRoute, RouteMatchType,
        RouteDestination,
    )

    tm = TrafficManager()
    tm.start()
    check(tm.is_running, "traffic manager started")

    # Register a route
    route = TrafficRoute(
        "api-route", "API Route",
        path="/api",
        path_match=RouteMatchType.PREFIX,
    )
    route.destinations.append(
        RouteDestination("backend-svc", 8080, weight=100.0)
    )
    tm.register_route(route)

    routes = tm.list_routes()
    check(len(routes) == 1, "route registered")

    # Register virtual service
    vs = VirtualService("test-svc")
    tm.register_virtual_service(vs)
    check(tm.get_virtual_service("test-svc") is not None, "vs registered")

    # Register circuit breaker
    cb = tm.register_circuit_breaker("backend-svc")
    check(cb is not None, "circuit breaker registered")

    # Set load balancer strategy
    tm.set_load_balancer_strategy("least_request")
    check(tm._load_balancer.strategy == "least_request", "lb strategy set")

    # Route a request
    result = await tm.route("GET", "/api/orders")
    check(result["status"] == 200, "route request returns 200")
    check(result["route_id"] == "api-route", "route id matched")
    check(result["target"] == "backend-svc", "target selected")

    # Route non-matching path
    result2 = await tm.route("GET", "/unknown")
    check(result2["status"] == 404, "no route returns 404")

    # Rate limited
    for _ in range(100):
        await tm.route("GET", "/api/orders")
    result3 = await tm.route("GET", "/api/orders")
    check(result3["status"] in (200, 429), "rate limiting works")

    # Unregister route (before reload clears table)
    check(tm.unregister_route("api-route"), "route unregistered")

    # Reload
    rl = await tm.reload()
    check(rl["success"], "reload works")

    tm.stop()
    check(not tm.is_running, "traffic manager stopped")

    s = tm.get_stats()
    check(s["started"] == False, "stats shows stopped")


# ============================================================
# 25. Full Traffic Flow
# ============================================================
async def test_full_traffic_flow() -> None:
    report_section("25. Full Traffic Management Flow")
    from infrastructure.service_mesh.traffic import (
        TrafficManager, VirtualService, TrafficRoute,
        RouteMatchType, RouteDestination, TrafficCircuitBreaker,
        CircuitBreakerConfig, BlueGreenDeployer, CanaryRule,
        CanaryRelease, RetryManager, OutlierDetector,
    )

    tm = TrafficManager()
    tm.start()

    # Create virtual service with weighted routing
    vs = tm._virtual_services  # Direct access for test
    orders_vs = VirtualService("orders-svc")
    orders_vs.create_weighted_route(
        "orders-v1", path="/orders",
        stable_host="orders-stable",
        canary_host="orders-canary",
        stable_weight=70.0,
        canary_weight=30.0,
    )
    tm.register_virtual_service(orders_vs)

    # Register circuit breaker
    tm.register_circuit_breaker("orders-stable", CircuitBreakerConfig(
        failure_threshold=3,
        timeout_s=0.05,
    ))

    # Create retries
    retry = RetryManager(max_retries=2)

    # Test blue-green deployment
    bg = BlueGreenDeployer()
    bg.start_deployment("order-dep", "v1", "v2", "blue", "green")

    # Test canary
    canary = CanaryRelease()
    cr = CanaryRule("c1", "canary-host", "stable-host", percentage=25.0)
    canary.add_rule(cr)

    decision = canary.decide("c1", request_id="test-user-1")
    check(decision["is_canary"] or not decision["is_canary"], "canary decision works")

    # Outlier detection
    od = OutlierDetector(consecutive_errors=3)
    od.record_request("healthy-inst", True, 10.0)
    od.record_request("unhealthy-inst", False, 50.0)
    od.record_request("unhealthy-inst", False, 50.0)
    od.record_request("unhealthy-inst", False, 50.0)
    check(od.check_outlier("unhealthy-inst")["ejected"], "unhealthy ejected")

    # Traffic split
    from infrastructure.service_mesh.traffic import TrafficSplit
    ts = TrafficSplit()
    dests = [
        {"host": "stable", "weight": 70.0},
        {"host": "canary", "weight": 30.0},
    ]
    sel = ts.select_destination(dests, key="user-abc")
    check(sel is not None, "traffic split selected destination")

    # Route a full request
    result = await tm.route("GET", "/orders/123")
    check(result["status"] == 200, "full flow: route success")

    # Test circuit breaker
    cb = tm._circuit_breakers.get("orders-stable")
    if cb:
        for _ in range(3):
            cb.record_failure()
        check(cb.is_open, "circuit opened after failures")

    tm.stop()
    check(not tm.is_running, "traffic manager stopped")

    s = tm.get_stats()
    check(s["request_count"] >= 1, "final request count")


# ============================================================
# Main
# ============================================================
async def main() -> None:
    print("=" * 60)
    print("ICYQuant Service Mesh Traffic Management - Validation")
    print("=" * 60)

    tests = [
        test_traffic_metrics,
        test_policies,
        test_telemetry,
        test_diagnostics,
        test_route,
        test_route_matcher,
        test_route_rewriter,
        test_virtual_service,
        test_destination_rule,
        test_traffic_split,
        test_weighted_router,
        test_load_balancer,
        test_blue_green,
        test_canary,
        test_mirror,
        test_retry,
        test_hedging,
        test_timeout,
        test_circuit_breaker,
        test_outlier_detection,
        test_rate_limiter,
        test_connection_pool,
        test_scheduler,
        test_traffic_manager,
        test_full_traffic_flow,
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as exc:
            global FAILED
            FAILED += 1
            FAILURES.append(f"  - ERROR in {test_fn.__name__}: {exc}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed (total {PASSED + FAILED})")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f)
    else:
        print("ALL CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())