"""Comprehensive validation tests for ICYQuant Service Mesh.

Tests all major components of the Service Mesh V1 implementation
including models, control plane, data plane, sidecar, proxy,
runtime, bootstrap, manager, discovery, configuration,
synchronization, and adapters.
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from typing import Any, Dict, List

# Ensure project root is in path
sys.path.insert(0, ".")

passed = 0
failed = 0
errors: List[str] = []


def check(condition: bool, label: str) -> None:
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        errors.append(f"FAIL: {label}")


def check_raises(
    exc_type: type,
    fn,
    label: str,
    *args,
    **kwargs,
) -> None:
    global passed, failed
    try:
        fn(*args, **kwargs)
        failed += 1
        errors.append(f"FAIL: {label} - no exception raised")
    except exc_type:
        passed += 1
    except Exception as e:
        failed += 1
        errors.append(
            f"FAIL: {label} - wrong exception: {e}"
        )


async def main() -> None:
    global passed, failed

    print("=" * 60)
    print("ICYQuant Service Mesh - Validation")
    print("=" * 60)

    # ── 1. Models ──
    print("\n=== 1. Mesh Models ===")
    from infrastructure.service_mesh import (
        MeshService,
        MeshServiceStatus,
        SidecarInstance,
        SidecarState,
        RoutingRule,
        ProxyConfig,
        ProxyProtocol,
        ProxyType,
        MeshMetadata,
    )

    svc = MeshService("oms", namespace="trading", version="v2")
    check(svc.service_id == "trading/oms", "service_id correct")
    check(svc.status == MeshServiceStatus.CREATED, "initial status")
    check(isinstance(svc.to_dict(), dict), "to_dict returns dict")
    check(svc.to_dict()["name"] == "oms", "to_dict includes name")

    si = SidecarInstance("sc-1", "oms", proxy_type=ProxyType.INTERNAL)
    check(si.state == SidecarState.CREATED, "sidecar initial state")
    check(si.to_dict()["sidecar_id"] == "sc-1", "sidecar to_dict")

    rule = RoutingRule(
        "rule-1", "oms", path="/api/orders", weight=0.8
    )
    check(rule.path == "/api/orders", "routing rule path")
    check(rule.weight == 0.8, "routing rule weight")
    check(rule.to_dict()["rule_id"] == "rule-1", "rule to_dict")

    pc = ProxyConfig(listen_port=15002, protocol=ProxyProtocol.GRPC)
    check(pc.listen_port == 15002, "proxy config port")
    check(pc.protocol == ProxyProtocol.GRPC, "proxy config protocol")
    check(pc.to_dict()["listen_port"] == 15002, "config to_dict")

    meta = MeshMetadata("test-mesh", version="2.0.0")
    check(meta.mesh_id == "test-mesh", "mesh metadata id")
    check(meta.to_dict()["version"] == "2.0.0", "metadata to_dict")

    # ── 2. MeshContext ──
    print("\n=== 2. MeshContext ===")
    from infrastructure.service_mesh import MeshContext

    mc = MeshContext()
    mc.register("component_a", {"key": "value"})
    check(mc.has("component_a"), "component registered")
    check(mc.get("component_a") == {"key": "value"}, "component get")
    check(not mc.has("nonexistent"), "non-existent component")
    mc.set_config("timeout", 30)
    check(mc.get_config("timeout") == 30, "config get/set")
    mc.set_metadata("version", "1.0")
    check(mc.get_metadata("version") == "1.0", "metadata get/set")
    stats = mc.get_stats()
    check(stats["component_count"] == 1, "stats component count")
    mc.clear()
    check(mc.get_stats()["component_count"] == 0, "clear empties")

    # ── 3. MeshEventPublisher ──
    print("\n=== 3. MeshEventPublisher ===")
    from infrastructure.service_mesh import MeshEvent, MeshEventPublisher

    pub = MeshEventPublisher()
    received: List[Dict[str, Any]] = []

    def handler(record):
        received.append(record)

    pub.subscribe(handler, [MeshEvent.MESH_STARTED, MeshEvent.SIDECAR_CREATED])
    pub.subscribe(lambda r: received.append(r))

    r1 = await pub.publish(MeshEvent.MESH_STARTED, {"test": True})
    check(r1["success"], "publish succeeded")
    check(r1["dispatched"] >= 2, "dispatched to at least 2 handlers")

    r2 = await pub.publish(MeshEvent.SIDECAR_CREATED, {"id": "sc-1"})
    check(r2["dispatched"] >= 2, "sidecar event dispatched")

    r3 = await pub.publish(MeshEvent.MESH_STOPPED)
    check(r3["dispatched"] >= 1, "global handler received mesh_stopped")

    check(len(received) >= 3, "all events received")
    pub_stats = pub.get_stats()
    check(pub_stats["publish_count"] == 3, "publish count is 3")
    history = pub.get_history(limit=10)
    check(len(history) >= 3, "history has events")

    # ── 4. MeshMetrics ──
    print("\n=== 4. MeshMetrics ===")
    from infrastructure.service_mesh import MeshMetrics

    mm = MeshMetrics()
    mm.increment_runtime_total()
    mm.increment_runtime_total()
    mm.increment_sidecar_total({"service": "oms"})
    mm.increment_proxy_request({"method": "GET"})
    mm.increment_configuration_total()
    mm.increment_reload_total()
    mm.set_gauge("active_sidecars", 5.0)
    mm.record_timer("proxy_latency", 0.025)

    check(mm.get_counter(MeshMetrics.RUNTIME_TOTAL) == 2, "runtime counter")
    check(mm.get_counter(MeshMetrics.SIDECAR_TOTAL) == 1, "sidecar counter")
    check(mm.get_gauge("active_sidecars") == 5.0, "gauge works")
    check(len(mm.get_timers("proxy_latency")) == 1, "timer recorded")

    summary = mm.get_summary()
    check(summary["counters"][MeshMetrics.RELOAD_TOTAL] == 1, "reload counter")

    # ── 5. MeshLifecycle & MeshState ──
    print("\n=== 5. MeshLifecycle ===")
    from infrastructure.service_mesh import MeshLifecycle, MeshState

    ml = MeshLifecycle()
    check(ml.state == MeshState.CREATED, "initial state is created")
    check(ml.can_transition_to(MeshState.BOOTSTRAPPED), "valid transition")
    check(not ml.can_transition_to(MeshState.RUNNING), "invalid transition blocked")

    r = ml.transition_to(MeshState.BOOTSTRAPPED, "bootstrap")
    check(r["success"], "transition to bootstrapped succeeded")
    check(ml.state == MeshState.BOOTSTRAPPED, "state updated to bootstrapped")

    r2 = ml.transition_to(MeshState.RUNNING, "start")
    check(r2["success"], "transition to running succeeded")
    check(ml.is_running, "is_running returns True")

    # Listeners
    transitions: List[Dict[str, Any]] = []

    def on_running(old, new, record):
        transitions.append(record)

    ml.on_state(MeshState.RELOADING, on_running)
    ml.transition_to(MeshState.RELOADING, "reload")
    ml.transition_to(MeshState.RUNNING, "reload_done")
    check(len(transitions) == 1, "listener fired once")

    # Invalid transition
    r3 = ml.transition_to(MeshState.BOOTSTRAPPED)
    check(not r3["success"], "invalid transition rejected")

    hist = ml.get_history()
    check(len(hist) >= 3, "history has transitions")
    durations = ml.get_durations()
    check(len(durations) >= 2, "durations tracked")

    ml.reset()
    check(ml.state == MeshState.CREATED, "reset works")

    # ── 6. ControlPlane ──
    print("\n=== 6. ControlPlane ===")
    from infrastructure.service_mesh import ControlPlane

    cp = ControlPlane()
    await cp.start()
    check(cp.is_running, "control plane running")

    rule = RoutingRule("r1", "oms", path="/orders")
    cp.add_routing_rule(rule)
    check(len(cp.get_routing_rules()) == 1, "rule added")
    check(len(cp.get_routing_rules(service="oms")) == 1, "filter by service")
    check(len(cp.get_routing_rules(service="risk")) == 0, "filter excludes")

    cp.set_security_policy("sec-1", {"mtls": True})
    cp.set_traffic_policy("tp-1", {"rate_limit": 100})
    cp.set_certificate_policy("cert-1", {"provider": "vault"})

    pub2 = MeshEventPublisher()
    cp.set_publisher(pub2)
    pub2.subscribe(lambda r: None)

    pub_result = await cp.publish_configuration("routing")
    check(pub_result["config_type"] == "routing", "publish config type")
    sync_result = await cp.synchronize()
    check(sync_result["success"], "synchronize succeeded")

    config = cp.get_configuration("all")
    check("rules" in config, "config has rules")

    check(cp.remove_routing_rule("r1"), "rule removed")
    check(len(cp.get_routing_rules()) == 0, "no rules after removal")

    cp_stats = cp.get_stats()
    check(cp_stats["running"], "control plane running in stats")

    await cp.stop()
    check(not cp.is_running, "control plane stopped")

    # ── 7. DataPlane & CircuitBreaker ──
    print("\n=== 7. DataPlane & CircuitBreaker ===")
    from infrastructure.service_mesh import CircuitBreaker, DataPlane

    cb = CircuitBreaker(failure_threshold=3, reset_timeout_s=0.01)
    check(not cb.is_open, "circuit initially closed")
    for _ in range(3):
        cb.record_failure()
    check(cb.is_open, "circuit open after failures")
    state = cb.get_state()
    check(state["open"], "state shows open")
    cb.reset()
    check(not cb.is_open, "reset closes circuit")

    dp = DataPlane()
    await dp.start()
    check(dp.is_running, "data plane running")

    rules = [
        RoutingRule("r1", "oms", path="/orders", retry_policy={"max_retries": 2, "backoff_ms": 1}),
        RoutingRule("r2", "risk", path="/risk"),
    ]
    dp.update_routing_rules(rules)

    result = await dp.intercept("GET", "/orders/123")
    check(result["status"] == 200, "intercept matched route")

    result2 = await dp.intercept("GET", "/unknown")
    check(result2["status"] == 404, "intercept returned 404 for unknown")

    upstream_result = await dp.forward("backend-1", "POST", "/data")
    check(upstream_result["status"] == 200, "forward succeeded")

    dp_stats = dp.get_stats()
    check(dp_stats["request_count"] >= 2, "requests tracked")

    await dp.stop()

    # ── 8. Sidecar ──
    print("\n=== 8. Sidecar ===")
    from infrastructure.service_mesh import Sidecar, SidecarState

    sc = Sidecar("sc-test", "oms")
    check(sc.state == SidecarState.CREATED, "sidecar created state")
    check(sc.sidecar_id == "sc-test", "sidecar id")

    pub3 = MeshEventPublisher()
    sc.set_publisher(pub3)
    pub3.subscribe(lambda r: None)

    await sc.start()
    check(sc.is_running, "sidecar is running")
    check(sc.state == SidecarState.RUNNING, "sidecar running state")

    hb = await sc.heartbeat()
    check(hb["success"], "heartbeat succeeded")

    resp = sc.handle_request("GET", "/api/test")
    check(resp["status"] == 200, "request handled by sidecar")

    # Reload
    reload_result = await sc.reload({"timeout": 60})
    check(reload_result["success"], "reload succeeded")
    check(sc.state == SidecarState.RUNNING, "state is running after reload")

    # Stop
    await sc.stop()
    check(sc.state == SidecarState.STOPPED, "sidecar stopped")

    sc_stats = sc.get_stats()
    check(sc_stats["service_name"] == "oms", "stats has service name")

    # ── 9. MeshProxy ──
    print("\n=== 9. MeshProxy ===")
    from infrastructure.service_mesh import MeshProxy

    mp = MeshProxy()
    await mp.start()
    check(mp.is_running, "proxy running")

    mp.add_upstream("backend-1", 8080, weight=0.7)
    mp.add_upstream("backend-2", 8081, weight=0.3)
    mp.add_upstream("backend-3", 8082, metadata={"primary": True})

    check(mp.remove_upstream("backend-3", 8082), "remove upstream")
    mp.set_upstream_health("backend-2", 8081, healthy=False)

    req = await mp.handle_request("GET", "/api/orders")
    check(req["status"] == 200, "proxy request handled")

    # Custom middleware
    def logging_mw(method, path, headers, body):
        return None  # pass through

    mp.add_middleware(logging_mw)

    resp = await mp.handle_response({"status": 200}, {"host": "127.0.0.1", "port": 8080})
    check(resp.get("_proxy_processed"), "response processed")

    mp_stats = mp.get_stats()
    check(mp_stats["upstream_count"] == 2, "upstream count is 2")
    check(mp_stats["healthy_upstreams"] == 1, "only 1 healthy upstream")

    await mp.stop()

    # ── 10. MeshRuntime ──
    print("\n=== 10. MeshRuntime ===")
    from infrastructure.service_mesh import MeshRuntime

    mr = MeshRuntime()
    pub4 = MeshEventPublisher()
    mr.set_publisher(pub4)
    pub4.subscribe(lambda r: None)

    start_res = await mr.start({"key": "value"})
    check(start_res["runtime"] == "started", "runtime started")
    check(mr.is_running, "runtime is running")

    reload_res = await mr.reload({"key": "updated"})
    check(reload_res["success"], "runtime reloaded")

    def handler(cfg):
        return True

    mr.register_reload_handler("test", handler)
    reload_res2 = await mr.reload()
    check(reload_res2["handler_results"].get("test", {}).get("success"), "handler executed")

    cfg = mr.get_config()
    check(cfg.get("key") == "updated", "config updated after reload")

    await mr.refresh_policies({"rate_limit": 100})
    check(mr.get_config().get("policies", {}).get("rate_limit") == 100, "policy refreshed")

    mr_stats = mr.get_stats()
    check(mr_stats["reload_count"] >= 2, "reload count tracked")

    await mr.stop()

    # ── 11. MeshBootstrap ──
    print("\n=== 11. MeshBootstrap ===")
    from infrastructure.service_mesh import MeshBootstrap, BootstrapPhase

    bs = MeshBootstrap()
    pub5 = MeshEventPublisher()
    bs.set_publisher(pub5)

    order: List[str] = []

    async def phase_fn(name):
        order.append(name)
        return {"phase": name}

    bs.register_phase(BootstrapPhase.CONFIGURATION, lambda: phase_fn("config"))
    bs.register_phase(BootstrapPhase.SERVICE_DISCOVERY, lambda: phase_fn("discovery"))
    bs.register_phase(BootstrapPhase.CONTROL_PLANE, lambda: phase_fn("control"))
    bs.register_phase(BootstrapPhase.DATA_PLANE, lambda: phase_fn("data"))
    bs.register_phase(BootstrapPhase.SIDECAR_RUNTIME, lambda: phase_fn("sidecar"))
    bs.register_phase(BootstrapPhase.MESH_READY, lambda: phase_fn("ready"))

    result = await bs.startup()
    check(result["bootstrapped"], "bootstrap succeeded")
    check(len(order) == 6, "all 6 phases executed")
    check(result["rollback_triggered"] == False, "no rollback needed")

    # Test rollback
    bs2 = MeshBootstrap()
    bs2.register_phase(BootstrapPhase.CONFIGURATION, lambda: phase_fn("config2"))

    async def fail_fn():
        raise RuntimeError("fail")

    bs2.register_phase(BootstrapPhase.REGISTRY if hasattr(BootstrapPhase, 'REGISTRY') else BootstrapPhase.CONTROL_PLANE, fail_fn)
    # Actually, let me use a proper phase
    bs3 = MeshBootstrap()
    bs3.register_phase(BootstrapPhase.CONFIGURATION, lambda: {"ok": True})
    bs3.register_phase(BootstrapPhase.CONTROL_PLANE, fail_fn)
    result2 = await bs3.startup()
    check(not result2["bootstrapped"], "bootstrap fails on error")
    check(result2["failed_phase"] == "control_plane", "failed phase identified")

    bs_stats = bs.get_stats()
    check(len(bs_stats["completed_phases"]) == 6, "all phases completed")

    # ── 12. MeshDiscovery ──
    print("\n=== 12. MeshDiscovery ===")
    from infrastructure.service_mesh import MeshDiscovery

    md = MeshDiscovery()
    svc = md.register_service("oms", namespace="trading", version="v2")
    check(svc.service_id == "trading/oms", "discovery service registered")
    check(md.get_service("trading/oms") is not None, "get_service works")

    svcs = md.list_services()
    check(len(svcs) == 1, "list has 1 service")
    svcs_trading = md.list_services(namespace="trading")
    check(len(svcs_trading) == 1, "filter by namespace works")
    svcs_risk = md.list_services(namespace="risk")
    check(len(svcs_risk) == 0, "filter excludes wrong namespace")

    # Routing rules in discovery
    rule = RoutingRule("dr1", "oms", path="/orders")
    md.add_routing_rule(rule)
    check(len(md.get_routing_rules()) == 1, "discovery routing rule added")

    sync_res = await md.sync()
    check(sync_res["success"], "sync succeeded")

    md_stats = md.get_stats()
    check(md_stats["services_count"] == 1, "discovery stats correct")

    check(md.deregister_service("trading/oms"), "deregister works")
    check(len(md.list_services()) == 0, "no services after deregister")

    # ── 13. MeshConfiguration ──
    print("\n=== 13. MeshConfiguration ===")
    from infrastructure.service_mesh import MeshConfiguration

    mc2 = MeshConfiguration()
    r1 = mc2.add_routing_rule("rule-1", "oms", path="/api/orders", weight=0.8)
    check(r1.rule_id == "rule-1", "rule created")
    check(len(mc2.get_routing_rules()) == 1, "1 rule exists")

    mc2.set_retry_policy("oms", max_retries=3, backoff_ms=200)
    retry = mc2.get_retry_policy("oms")
    check(retry["max_retries"] == 3, "retry policy set")

    mc2.set_timeout_policy("oms", timeout_s=60.0)
    check(mc2.get_timeout_policy("oms") == 60.0, "timeout policy set")

    mc2.set_security_policy("sec-1", {"mtls": True})
    mc2.set_traffic_policy("tp-1", {"rate_limit": 200})

    all_cfg = mc2.get_all_configuration()
    check("routing_rules" in all_cfg, "all config has routing")
    check(all_cfg["version"] >= 1, "version incremented")

    # Apply from dict
    new_cfg = {
        "routing_rules": [
            {"rule_id": "rule-2", "service": "risk", "path": "/risk"}
        ],
        "retry_policies": {"risk": {"max_retries": 1}},
    }
    mc2.apply_configuration(new_cfg)
    check(len(mc2.get_routing_rules()) == 2, "now 2 rules after apply")

    mc2_stats = mc2.get_stats()
    check(mc2_stats["routing_rules"] == 2, "stats shows 2 rules")

    # ── 14. MeshRegistry ──
    print("\n=== 14. MeshRegistry ===")
    from infrastructure.service_mesh import MeshRegistry

    mr2 = MeshRegistry()
    svc1 = mr2.register_service("oms", namespace="trading")
    check(svc1.service_id == "trading/oms", "registry service id")
    svc2 = mr2.register_service("risk", namespace="trading")
    check(svc2.service_id == "trading/risk", "second service registered")

    mr2.add_sidecar_to_service("trading/oms", "sc-oms-1")
    mr2.add_sidecar_to_service("trading/oms", "sc-oms-2")
    sidecars = mr2.get_service_sidecars("trading/oms")
    check(len(sidecars) == 2, "service has 2 sidecars")

    discovered = mr2.discover("oms", namespace="trading")
    check(len(discovered) == 1, "discover found oms")
    discovered_all = mr2.discover()
    check(len(discovered_all) == 2, "discover all returns 2")

    dereg = mr2.deregister_service("trading/risk")
    check(dereg["success"], "deregister succeeded")
    check(len(mr2.list_services()) == 1, "1 service remaining")

    mr2_stats = mr2.get_stats()
    check(mr2_stats["registered_services"] == 1, "registry stats correct")

    # ── 15. MeshSynchronizer ──
    print("\n=== 15. MeshSynchronizer ===")
    from infrastructure.service_mesh import MeshSynchronizer

    ms = MeshSynchronizer()
    pub6 = MeshEventPublisher()
    ms.set_publisher(pub6)
    pub6.subscribe(lambda r: None)

    sync_results: List[Dict[str, Any]] = []

    async def sync_handler():
        sync_results.append({"synced": True})
        return {"count": len(sync_results)}

    ms.register_sync_handler("control_plane", sync_handler)
    ms.register_sync_handler("data_plane", lambda: {"done": True})

    result = await ms.synchronize()
    check(result["all_successful"], "synchronize all succeeded")
    check(len(sync_results) >= 1, "handler was called")

    # Start/stop auto sync
    await ms.start_auto_sync(interval_s=0.01)
    check(ms.is_running, "auto sync started")
    await asyncio.sleep(0.05)
    await ms.stop_auto_sync()
    check(not ms.is_running, "auto sync stopped")

    ms_stats = ms.get_stats()
    check(ms_stats["sync_count"] >= 1, "sync count tracked")

    # ── 16. MeshManager ──
    print("\n=== 16. MeshManager ===")
    from infrastructure.service_mesh import MeshManager, ProxyType

    mm = MeshManager()
    create_result = await mm.create_mesh({"test": True})
    check(create_result["bootstrapped"], "mesh created via manager")

    sc_oms = await mm.create_sidecar("sc-oms", "oms", proxy_type=ProxyType.INTERNAL)
    check(sc_oms.is_running, "sidecar created and running")
    check(len(mm.list_sidecars()) == 1, "manager has 1 sidecar")

    sc_list = mm.list_sidecars(service_name="oms")
    check(len(sc_list) == 1, "filter sidecars by service")

    sc_destroy = await mm.destroy_sidecar("sc-oms")
    check(sc_destroy["success"], "sidecar destroyed")
    check(len(mm.list_sidecars()) == 0, "no sidecars after destroy")

    # Reload
    reload_result = await mm.reload({"key": "val"})
    check(reload_result["success"], "manager reload works")

    mesh_info = mm.get_mesh_info()
    check(mesh_info["created"], "mesh created status")

    # Destroy
    destroy_result = await mm.destroy_mesh()
    check(destroy_result["success"], "mesh destroyed")

    # ── 17. ServiceMesh (full lifecycle) ──
    print("\n=== 17. ServiceMesh Full Lifecycle ===")
    from infrastructure.service_mesh import ServiceMesh

    sm = ServiceMesh(mesh_id="test-mesh", config={"feature": True})
    check(sm.metadata.mesh_id == "test-mesh", "mesh id set")

    startup_result = await sm.startup()
    check(startup_result["bootstrapped"], "service mesh started")
    check(sm.is_running, "service mesh is running")
    check(sm.lifecycle.state == MeshState.RUNNING, "lifecycle is running")

    # Create sidecar through mesh
    sc_test = await sm.create_sidecar("sc-test", "oms")
    check(sc_test.is_running, "sidecar created via mesh")

    # Handle request
    req_result = await sm.handle_request("GET", "/api/orders")
    check(req_result["status"] == 200, "mesh request handled")

    # Health check
    health = await sm.health_check()
    check("components" in health, "health has components")
    check("control_plane" in health["components"], "has control_plane check")

    # Reload
    reload_result2 = await sm.reload({"new_config": "value"})
    check(reload_result2["success"], "mesh reloaded")

    # Shutdown
    shutdown_result = await sm.shutdown()
    check(shutdown_result["success"], "mesh shutdown succeeded")
    check(not sm.is_running, "mesh no longer running")

    # Stats
    sm_stats = sm.get_stats()
    check("bootstrap" in sm_stats, "stats has bootstrap info")

    # ── 18. Adapters ──
    print("\n=== 18. Adapters ===")
    from infrastructure.service_mesh import (
        InternalProxyAdapter,
        EnvoyProxyAdapter,
        MockProxyAdapter,
    )

    ipa = InternalProxyAdapter()
    await ipa.start()
    check(ipa.is_running, "internal adapter running")
    forward_result = await ipa.forward("backend", "GET", "/test")
    check(forward_result["status"] == 200, "internal forward works")

    def custom_handler(method, path, headers, body):
        return {"status": 201, "body": {"custom": True}}

    ipa.register_handler("/custom", custom_handler)
    custom_res = await ipa.forward("backend", "GET", "/custom/path")
    check(custom_res["status"] == 201, "custom handler works")
    await ipa.stop()

    # Envoy stub
    epa = EnvoyProxyAdapter()
    await epa.start()
    check(epa.is_running, "envoy adapter running (stub)")
    cluster_res = await epa.configure_cluster(
        "test-cluster", [{"host": "127.0.0.1", "port": 8080}]
    )
    check(cluster_res["success"], "envoy cluster configured")
    listener_res = await epa.configure_listener(
        "test-listener", 8080, [{"route": "/test"}]
    )
    check(listener_res["success"], "envoy listener configured")
    envoy_forward = await epa.forward("test", "GET", "/path")
    check(envoy_forward["body"]["adapter"] == "envoy_stub", "envoy forward uses stub")
    await epa.stop()

    # Mock adapter
    mpa = MockProxyAdapter()
    await mpa.start()
    check(mpa.is_running, "mock adapter running")

    mpa.set_response("/api/special", {"status": 200, "body": {"special": True}})
    special_res = await mpa.forward("test", "GET", "/api/special")
    check(special_res["body"]["special"], "mock custom response")

    mpa.set_failure("/api/fail", 1.0)  # 100% failure
    fail_res = await mpa.forward("test", "GET", "/api/fail")
    check(fail_res["status"] == 500, "mock failure injection works")

    mpa.set_latency(0.01)
    default_res = await mpa.forward("test", "GET", "/other")
    check(default_res["_mock"], "mock default response")

    request_log = mpa.get_request_log()
    check(len(request_log) >= 3, "mock request log has entries")
    await mpa.stop()

    # ── 19. MeshDiagnostics ──
    print("\n=== 19. MeshDiagnostics ===")
    from infrastructure.service_mesh import MeshDiagnostics

    md2 = MeshDiagnostics()
    md2.report_issue("critical", "control_plane", "connection_lost", "Cannot connect to backing service")
    md2.report_issue("warning", "data_plane", "high_latency", "Proxy latency above threshold")
    md2.report_issue("info", "sidecar", "reload", "Sidecar configuration reloaded")

    check_result = md2.check()
    check(check_result["critical_count"] == 1, "1 critical issue")
    check(check_result["warning_count"] == 1, "1 warning issue")

    issues = md2.get_issues(severity="critical")
    check(len(issues) == 1, "filter critical issues")

    diag_stats = md2.get_stats()
    check(diag_stats["total_issues"] == 3, "3 total issues")

    # ── 20. MeshTelemetry ──
    print("\n=== 20. MeshTelemetry ===")
    from infrastructure.service_mesh import MeshTelemetry

    mt = MeshTelemetry()
    mt.log_sidecar_lifecycle("sc-1", "started")
    mt.log_configuration_sync("routing", "success", 0.05)
    mt.log_proxy_request("sc-1", "GET", "/api/orders", 200, 0.025)
    mt.log_mesh_event("start", "service_mesh")
    mt.log_error("data_plane", "timeout", "Request timed out")

    records = mt.get_records()
    check(len(records) >= 5, "telemetry has 5 records")

    error_records = mt.get_error_records()
    check(len(error_records) >= 1, "error records exist")

    config_records = mt.get_records(category="config_sync")
    check(len(config_records) >= 1, "config sync records exist")

    mt_stats = mt.get_stats()
    check(mt_stats["total_records"] >= 5, "telemetry stats correct")

    # ── 21. MeshHealth (deep check) ──
    print("\n=== 21. MeshHealth ===")
    from infrastructure.service_mesh import MeshHealth

    mh = MeshHealth()
    check_result = await mh.check()
    check(check_result["healthy"], "all components healthy")
    check(check_result["total"] == 5, "5 components checked")

    # Register a custom check
    mh.register_check("custom", lambda: {"healthy": True})
    check_result2 = await mh.check()
    check(check_result2["total"] == 6, "6 components after custom check")

    # Unhealthy component
    mh.register_check("unhealthy", lambda: False)
    check_result3 = await mh.check()
    check(not check_result3["healthy"], "unhealthy detected")
    check(check_result3["unhealthy_count"] == 1, "1 unhealthy component")

    unhealthy = mh.get_unhealthy_components()
    check("unhealthy" in unhealthy, "unhealthy component identified")

    history = mh.get_history()
    check(len(history) >= 3, "health history has records")

    mh.unregister_check("unhealthy")
    check_result4 = await mh.check()
    check(check_result4["healthy"], "healthy again after unregister")

    # ── 22. Full Mesh Boot → Run → Reload → Stop ──
    print("\n=== 22. Full Mesh Boot-Run-Reload-Stop Cycle ===")

    sm2 = ServiceMesh(mesh_id="production-mesh", config={"env": "prod"})
    boot = await sm2.startup()
    check(boot["bootstrapped"], "production mesh boot succeeded")
    check(sm2.is_running, "production mesh running")

    # Create multiple sidecars
    sc_a = await sm2.create_sidecar("sc-order", "order_service")
    sc_b = await sm2.create_sidecar("sc-risk", "risk_service")
    check(sc_a.is_running and sc_b.is_running, "both sidecars running")

    # Make requests through mesh
    r1 = await sm2.handle_request("GET", "/orders/123")
    check(r1["status"] == 200, "order request proxied")
    r2 = await sm2.handle_request("POST", "/risk/evaluate")
    check(r2["status"] == 200, "risk request proxied")

    # Health
    hc = await sm2.health_check()
    check(hc["healthy"], f"production mesh healthy (unhealthy: {hc.get('unhealthy_count', '?')}, components: {hc.get('components', {})})")

    # Reload
    rl = await sm2.reload({"timeout": 60, "retries": 3})
    check(rl["success"], "production mesh reloaded")

    # Shutdown
    sd = await sm2.shutdown()
    check(sd["success"], "production mesh shutdown succeeded")
    check(not sm2.is_running, "production mesh stopped")

    # Verify stats have full lifecycle data
    full_stats = sm2.get_stats()
    check(full_stats["metadata"]["mesh_id"] == "production-mesh", "mesh id preserved")

    # ── Final Summary ──
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed} passed, {failed} failed (total {total})")
    print("=" * 60)

    if errors:
        print("\nFAILURES:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nALL CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
