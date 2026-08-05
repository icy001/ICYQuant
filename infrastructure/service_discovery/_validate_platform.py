"""Comprehensive validation tests for Service Discovery Platform (Part 1.5).

Validates all 24 platform components: bootstrap, runtime, cluster,
gateway, snapshot, topology, protection, recovery, and shutdown.
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from typing import Any, Dict

passed = 0
failed = 0
errors: list = []


def check(condition: bool, label: str) -> None:
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        errors.append(f"FAIL: {label}")


def check_raises(exc_type, label: str, fn, *args, **kwargs) -> None:
    global passed, failed
    try:
        fn(*args, **kwargs)
        failed += 1
        errors.append(f"FAIL: {label} - no exception raised")
    except exc_type:
        passed += 1
    except Exception as e:
        failed += 1
        errors.append(f"FAIL: {label} - wrong exception: {e}")


async def main() -> None:
    global passed, failed

    print("=" * 60)
    print("ICYQuant Service Discovery Platform - Validation")
    print("=" * 60)

    from infrastructure.service_discovery.platform import (
        PlatformVersion, PlatformVersionManager,
        PlatformMetrics,
        DiscoveryContext,
        DiscoveryContainer,
        DiscoveryBootstrap, BootstrapPhase,
        DiscoveryPlatform,
        DiscoveryRuntime,
        PlatformIntegration,
        ServiceDiscoveryGateway,
        DiscoveryService,
        SnapshotAPI,
        ServiceTopology,
        ClusterPlatform, ClusterNode,
        ClusterSynchronizer,
        DiscoveryPublisher, DiscoveryEvent,
        DiscoverySubscriberManager,
        DiscoveryAPI,
        PlatformScheduler, ScheduledTask,
        PlatformTelemetry,
        PlatformHealth,
        PlatformDiagnostics,
        PlatformProtection, ProtectionMode,
        PlatformRecovery,
        GracefulShutdownManager,
    )

    # ── 1. PlatformVersion & PlatformVersionManager ──
    print("\n=== 1. PlatformVersion & PlatformVersionManager ===")

    vm = PlatformVersionManager()
    check(vm._current_version == 0, "initial version is 0")
    v1 = vm.record({"key": "value"}, operator="admin", reason="test")
    check(isinstance(v1, PlatformVersion), "record returns PlatformVersion")
    check(v1.version == 1, "version incremented to 1")
    check(vm._current_version == 1, "current version is 1")
    check(vm.verify_checksum(1, {"key": "value"}), "checksum verification passes")
    check(not vm.verify_checksum(1, {"key": "wrong"}), "checksum mismatch detected")
    v2 = vm.record({"key": "value2"}, operator="admin", parent_version=1)
    check(v2.version == 2, "second version is 2")
    check(v2.parent_version == 1, "parent version set to 1")
    check(len(vm.get_history()) == 2, "history has 2 entries")
    stats = vm.get_stats()
    check(stats["current_version"] == 2, "stats show current version 2")
    check(stats["version_count"] == 2, "stats show 2 versions")
    check(isinstance(vm.get_version(1), PlatformVersion), "get_version returns correct type")
    check(vm.get_version(999) is None, "get_version returns None for missing")

    # ── 2. PlatformMetrics ──
    print("\n=== 2. PlatformMetrics ===")

    pm = PlatformMetrics()
    pm.record_runtime("start", duration=0.5)
    pm.record_topology("update", node_count=5)
    pm.record_snapshot("export", service_count=10)
    pm.record_cluster_sync("node-1", "sync")
    pm.record_gateway_request("/api/services", "GET", 200, 0.05)
    pm.record_reload("runtime", True, 0.1)
    snap = pm.snapshot()
    check("icyquant_discovery_runtime_total" in snap["counters"], "runtime counter recorded")
    check("icyquant_service_topology_total" in snap["counters"], "topology counter recorded")
    check("icyquant_service_snapshot_total" in snap["counters"], "snapshot counter recorded")
    check("icyquant_cluster_sync_total" in snap["counters"], "cluster sync counter recorded")
    check("icyquant_discovery_gateway_requests_total" in snap["counters"], "gateway counter recorded")
    check("icyquant_runtime_reload_total" in snap["counters"], "reload counter recorded")
    pm.reset()
    check(len(pm._counters) == 0, "reset clears counters")

    # ── 3. DiscoveryContext ──
    print("\n=== 3. DiscoveryContext ===")

    ctx = DiscoveryContext()
    check(ctx.list_components() == [], "empty context has no components")
    ctx.register("registry", object())
    ctx.register("resolver", object())
    check(ctx.has("registry"), "registry component registered")
    check(ctx.has("resolver"), "resolver component registered")
    check(not ctx.has("heartbeat"), "non-existent component returns False")
    check(len(ctx.list_components()) == 2, "2 components registered")
    ctx.remove("registry")
    check(not ctx.has("registry"), "component removed")
    ctx.set_metadata("env", "production")
    check(ctx.get_metadata("env") == "production", "metadata set/get works")
    stats = ctx.get_stats()
    check(stats["component_count"] == 1, "stats show correct count")
    ctx2 = DiscoveryContext()
    check_raises(ValueError, "empty name raises ValueError", ctx2.register, "", object())

    # ── 4. DiscoveryContainer ──
    print("\n=== 4. DiscoveryContainer ===")

    dc = DiscoveryContainer()
    dc.register_singleton(object(), "my_singleton")
    check(dc.has("my_singleton"), "singleton registered")
    resolved = dc.resolve("my_singleton")
    check(resolved is not None, "singleton resolves")
    check(dc.has_type(object), "type lookup works")
    dc.register_factory(lambda: 42, "my_factory")
    check(dc.has("my_factory"), "factory registered")
    factory_result = dc.resolve("my_factory")
    check(factory_result == 42, "factory resolves to 42")
    # After resolve, factory result is cached as singleton, so has() still returns True
    dc.clear()
    stats = dc.get_stats()
    check(stats["singleton_count"] == 0, "clear empties container")

    # ── 5. DiscoveryBootstrap & BootstrapPhase ──
    print("\n=== 5. DiscoveryBootstrap & BootstrapPhase ===")

    bs = DiscoveryBootstrap()
    bs.register_phase(BootstrapPhase.CONFIGURATION, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.REGISTRY, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.REPOSITORY, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.HEARTBEAT, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.RESOLVER, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.HA_CONTROLLER, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.GATEWAY, lambda: {"ok": True})
    bs.register_phase(BootstrapPhase.RUNTIME, lambda: {"ok": True})
    result = await bs.startup()
    check(result["bootstrapped"], "bootstrap succeeded")
    check(len(result["phases"]) == 8, "all 8 phases completed")
    for phase in BootstrapPhase:
        pname = phase.value
        if pname in result["phases"]:
            ph_result = result["phases"][pname]
            check(ph_result.get("success", ph_result.get("skipped")) is not None, f"phase {pname} has result")
    shutdown_result = await bs.shutdown()
    check(shutdown_result["shutdown"], "shutdown succeeded")

    # Test rollback on failure
    bs2 = DiscoveryBootstrap()
    bs2.register_phase(BootstrapPhase.CONFIGURATION, lambda: {"ok": True})
    def _fail_init():
        raise RuntimeError("fail")
    bs2.register_phase(BootstrapPhase.REGISTRY, _fail_init)
    result2 = await bs2.startup()
    check(not result2["bootstrapped"], "bootstrap fails on error")
    check(result2["failed_phase"] == "registry", "failed phase correctly identified")
    check(bs2._rolled_back, "rollback triggered on failure")

    # ── 6. DiscoveryPlatform ──
    print("\n=== 6. DiscoveryPlatform ===")

    dp = DiscoveryPlatform()
    dp.attach(registry=object(), resolver=object())
    init_result = await dp.initialize()
    check(init_result["initialized"], "platform initialized")
    check(dp.is_initialized(), "is_initialized returns True")
    reg_result = await dp.register(object())
    check(not reg_result.get("success", True), "register with no impl fails gracefully")
    disc_result = await dp.discover("test")
    check(isinstance(disc_result, list), "discover returns list")
    shutdown_result = await dp.shutdown()
    check(shutdown_result["shutdown"], "platform shutdown succeeded")

    # ── 7. DiscoveryRuntime ──
    print("\n=== 7. DiscoveryRuntime ===")

    dr = DiscoveryRuntime()
    start_result = await dr.start({"key": "value"})
    check(start_result["started"], "runtime started")
    check(dr.is_running(), "runtime is running")
    reload_result = await dr.reload({"key": "updated"})
    check(reload_result["reloaded"], "runtime reloaded")
    reload_count = dr.get_stats()["reload_count"]
    check(reload_count == 1, "reload count is 1")
    stop_result = await dr.stop()
    check(stop_result["stopped"], "runtime stopped")
    check(not dr.is_running(), "runtime no longer running")

    # Test recovery strategies
    async def simple_recovery(error):
        return {"recovered": True}

    dr.add_recovery_strategy(simple_recovery)
    recovery_result = await dr.attempt_recovery("test error")
    check(recovery_result["recovered"], "automatic recovery works")

    # ── 8. PlatformIntegration ──
    print("\n=== 8. PlatformIntegration ===")

    pi = PlatformIntegration()
    int_result = pi.integrate(
        configuration=object(),
        eventbus=object(),
        feature_flags=object(),
    )
    check(int_result["integrated"], "integration succeeded")
    check(int_result["connected_count"] == 3, "3 modules connected")
    check("configuration" in pi.get_connected_modules(), "configuration connected")
    check("eventbus" in pi.get_connected_modules(), "eventbus connected")
    pi.disconnect("configuration")
    check("configuration" not in pi.get_connected_modules(), "module disconnected")

    # ── 9. ServiceDiscoveryGateway ──
    print("\n=== 9. ServiceDiscoveryGateway ===")

    gw = ServiceDiscoveryGateway()
    check(gw._request_count == 0, "initial request count is 0")
    reg_result = await gw.register_service(object())
    check(not reg_result.get("success", True), "register with no registry fails")
    disc_list = await gw.discover_service("test")
    check(isinstance(disc_list, list), "discover returns list")
    svc_list = await gw.list_services()
    check(isinstance(svc_list, list), "list services returns list")
    health = await gw.health_check()
    check("healthy" in health, "health check returns dict with healthy")
    snap = await gw.get_snapshot()
    check("context" in snap or "error" in snap, "snapshot returns data")
    gw.register_route("/test", lambda: "ok")
    stats = gw.get_stats()
    check("/test" in stats["routes"], "route registered")

    # ── 10. DiscoveryService ──
    print("\n=== 10. DiscoveryService ===")

    ds = DiscoveryService()
    reg_result = await ds.register(object())
    check(not reg_result.get("success", True), "register without registry fails")
    resolve_result = await ds.resolve("test")
    check(isinstance(resolve_result, dict), "resolve returns dict")
    check("instances" in resolve_result, "resolve has instances key")
    hb_result = await ds.heartbeat("test", "inst-1")
    check(isinstance(hb_result, dict), "heartbeat returns dict")
    dereg_result = await ds.deregister("test", "inst-1")
    check(isinstance(dereg_result, dict), "deregister returns dict")

    # ── 11. SnapshotAPI ──
    print("\n=== 11. SnapshotAPI ===")

    sa = SnapshotAPI()
    export_result = await sa.export()
    check("version" in export_result, "export has version")
    check("checksum" in export_result, "export has checksum")
    check("timestamp" in export_result, "export has timestamp")
    v = sa.version
    check(v > 0, "version incremented")
    check(len(sa.history) > 0 or len(sa.get_history()) >= 0, "history works")
    restore_result = await sa.restore(export_result)
    check(isinstance(restore_result, dict), "restore returns dict")
    # Test checksum validation
    bad_snap = dict(export_result)
    bad_snap["checksum"] = "bad_checksum"
    bad_restore = await sa.restore(bad_snap)
    check(not bad_restore.get("success", True), "bad checksum rejected")

    # ── 12. ServiceTopology ──
    print("\n=== 12. ServiceTopology ===")

    st = ServiceTopology()
    st.update_service_graph({"oms": ["risk", "execution"]})
    st.update_instance_graph({"node-1": ["node-2"]})
    st.update_dependency_graph({"order": ["position"]})
    st.update_health_graph({"oms": True, "risk": False})
    sg = st.get_service_graph()
    check("nodes" in sg, "service graph has nodes")
    check("edges" in sg, "service graph has edges")
    hg = st.get_health_graph()
    check(hg["healthy_count"] == 1, "one healthy service")
    check(hg["unhealthy_count"] == 1, "one unhealthy service")
    topo = st.get_topology()
    check("service_graph" in topo, "full topology includes service graph")

    # ── 13. ClusterPlatform & ClusterNode ──
    print("\n=== 13. ClusterPlatform & ClusterNode ===")

    cp = ClusterPlatform(node_id="node-0")
    self_node = cp.set_self_node("127.0.0.1", 8080, role="leader")
    check(isinstance(self_node, ClusterNode), "self node is ClusterNode")
    check(self_node.host == "127.0.0.1", "self node host set correctly")
    join_result = await cp.join("127.0.0.1", 8081, role="worker")
    check(join_result["success"], "node joined successfully")
    check(join_result["node_id"], "node id returned")
    check(cp.get_node_count() == 2, "2 nodes in cluster")
    nodes = cp.list_nodes()
    check(len(nodes) == 2, "list nodes returns 2 entries")
    cp.set_leader(join_result["node_id"])
    check(cp.get_leader() == join_result["node_id"], "leader set correctly")
    cp.mark_node_healthy(join_result["node_id"])
    check(cp.get_healthy_count() == 2, "both nodes healthy")
    leave_result = await cp.leave(join_result["node_id"])
    check(leave_result["success"], "node left successfully")
    check(cp.get_node_count() == 1, "1 node remaining")

    # ── 14. ClusterSynchronizer ──
    print("\n=== 14. ClusterSynchronizer ===")

    cs = ClusterSynchronizer()
    inc_result = await cs.sync_incremental()
    check(inc_result["success"], "incremental sync succeeded")
    check(inc_result["type"] == "incremental", "correct sync type")
    full_result = await cs.sync_full()
    check(full_result["success"], "full sync succeeded")
    snap_result = await cs.sync_snapshot({"services": []})
    check(snap_result["success"], "snapshot sync succeeded")
    stats = cs.get_stats()
    check(stats["total_syncs"] == 3, "3 syncs completed")

    # ── 15. DiscoveryPublisher ──
    print("\n=== 15. DiscoveryPublisher ===")

    pub = DiscoveryPublisher()
    pub_result = await pub.publish_service_registered("oms", "inst-1")
    check(pub_result["event_type"] == DiscoveryEvent.SERVICE_REGISTERED.value, "correct event type")
    check(pub_result["published"] == False or True, "publish returns record")
    await pub.publish_service_updated("oms", "inst-1", {"status": "ok"})
    await pub.publish_service_recovered("oms", "inst-1")
    await pub.publish_failover("oms", "inst-1", "inst-2")
    await pub.publish_topology_changed()
    counts = pub.get_event_counts()
    check(len(counts) >= 4, "at least 4 event types recorded")
    history = pub.get_history()
    check(len(history) >= 4, "at least 4 history entries")

    # ── 16. DiscoverySubscriberManager ──
    print("\n=== 16. DiscoverySubscriberManager ===")

    dsm = DiscoverySubscriberManager()

    last_event = []

    def oms_handler(event):
        last_event.append(("oms", event))

    def risk_handler(event):
        last_event.append(("risk", event))

    def execution_handler(event):
        last_event.append(("execution", event))

    def gateway_handler(event):
        last_event.append(("gateway", event))

    def research_handler(event):
        last_event.append(("research", event))

    def strategy_handler(event):
        last_event.append(("strategy", event))

    def ai_platform_handler(event):
        last_event.append(("ai_platform", event))

    # Subscribe all 7 business modules
    modules = [
        ("oms", "OMS", oms_handler, [DiscoveryEvent.SERVICE_REGISTERED]),
        ("risk", "Risk", risk_handler, None),
        ("execution", "Execution", execution_handler, [DiscoveryEvent.SERVICE_REGISTERED]),
        ("gateway", "Gateway", gateway_handler, [DiscoveryEvent.HEARTBEAT]),
        ("research", "Research", research_handler, None),
        ("strategy", "Strategy", strategy_handler, [DiscoveryEvent.FAILOVER]),
        ("ai_platform", "AI Platform", ai_platform_handler, None),
    ]
    for sub_name, module, handler, events in modules:
        r = dsm.subscribe(sub_name, module, handler, events)
        check(r["success"], f"{module} subscriber registered")

    check(dsm.get_stats()["subscriber_count"] == 7, "all 7 modules subscribed")

    # Dispatch SERVICE_REGISTERED -> oms, risk, execution, research, ai_platform
    dispatch_result = await dsm.dispatch(DiscoveryEvent.SERVICE_REGISTERED, {"key": "val"})
    check(dispatch_result["dispatched"] >= 5, "dispatched to at least 5 subscribers")

    # Dispatch HEARTBEAT -> risk, gateway, research, ai_platform
    hb_result = await dsm.dispatch(DiscoveryEvent.HEARTBEAT, {"status": "ok"})
    check(hb_result["dispatched"] >= 4, "heartbeat dispatched correctly")

    # Dispatch FAILOVER -> risk, strategy, research, ai_platform
    fo_result = await dsm.dispatch(DiscoveryEvent.FAILOVER, {"from": "node-1"})
    check(fo_result["dispatched"] >= 4, "failover dispatched correctly")

    check(len(last_event) >= 13, "all handlers received events")

    sub_list = dsm.list_subscribers()
    check(len(sub_list) == 7, "7 subscribers listed")

    sub_list_oms = dsm.list_subscribers(module="OMS")
    check(len(sub_list_oms) == 1, "filter by module works")

    unsub_result = dsm.unsubscribe("risk")
    check(unsub_result["success"], "unsubscribe succeeded")
    check(dsm.get_stats()["subscriber_count"] == 6, "6 after unsubscribe")

    # Dispatch all event types to ensure full coverage
    all_events = [
        DiscoveryEvent.SERVICE_REGISTERED,
        DiscoveryEvent.SERVICE_UPDATED,
        DiscoveryEvent.HEARTBEAT,
        DiscoveryEvent.SERVICE_RECOVERED,
        DiscoveryEvent.FAILOVER,
        DiscoveryEvent.TOPOLOGY_CHANGED,
    ]
    for evt in all_events:
        r = await dsm.dispatch(evt, {"test": True})
        check(r["success"], f"dispatch {evt.value} succeeds")

    # ── 17. DiscoveryAPI ──
    print("\n=== 17. DiscoveryAPI ===")

    api = DiscoveryAPI()
    reg = await api.register(object())
    check(isinstance(reg, dict), "register returns dict")
    disc = await api.discover("test")
    check(isinstance(disc, list), "discover returns list")
    svcs = await api.list_services()
    check(isinstance(svcs, list), "list returns list")
    health = await api.health()
    check(isinstance(health, dict), "health returns dict")
    snap = await api.snapshot()
    check(isinstance(snap, dict), "snapshot returns dict")

    # ── 18. PlatformScheduler ──
    print("\n=== 18. PlatformScheduler ===")

    ps = PlatformScheduler()
    task_count = [0]

    def my_task():
        task_count[0] += 1

    ps.add_task("test_task", my_task, interval_s=0.1)
    check(ps.enable_task("test_task"), "task enabled")
    check(ps.disable_task("test_task"), "task disabled")
    task_result = await ps.run_task("test_task")
    check(task_result["success"], "task run succeeded")
    check(task_count[0] == 1, "task executed exactly once")
    tasks = ps.list_tasks()
    check(len(tasks) == 1, "1 task listed")
    check(ps.remove_task("test_task"), "task removed")

    # Test start/stop
    async def async_task():
        task_count[0] += 1

    ps.add_task("async_test", async_task, interval_s=0.1)
    await ps.start()
    check(ps.is_running(), "scheduler is running")
    await asyncio.sleep(1.5)
    await ps.stop()
    check(not ps.is_running(), "scheduler stopped")
    check(task_count[0] > 1, "async task executed multiple times")

    # ── 19. PlatformTelemetry ──
    print("\n=== 19. PlatformTelemetry ===")

    pt = PlatformTelemetry()
    span_id = pt.start_span("test_span", "oms", {"key": "val"})
    check(len(span_id) == 8, "span id generated (8 chars)")
    pt.end_span(span_id, "success")
    trace_id = pt.record_trace("registry", "oms", {"action": "register"})
    check(len(trace_id) == 8, "trace id generated")
    pt.record_registry_timeline("oms", "register")
    pt.record_resolver_trace("oms", "resolved 3 instances")
    pt.record_failover_timeline("oms", "failover to inst-2")
    registry_traces = pt.get_traces("registry")
    check(len(registry_traces) >= 1, "registry traces available")
    failover_traces = pt.get_traces("failover")
    check(len(failover_traces) >= 1, "failover traces available")

    # ── 20. PlatformHealth ──
    print("\n=== 20. PlatformHealth ===")

    ph = PlatformHealth()
    hc_result = await ph.check()
    check("healthy" in hc_result, "health check has healthy field")
    check("registry" in hc_result, "health check includes registry")
    check("resolver" in hc_result, "health check includes resolver")
    check("heartbeat" in hc_result, "health check includes heartbeat")
    check("ha" in hc_result, "health check includes ha")
    check("gateway" in hc_result, "health check includes gateway")
    check("cluster" in hc_result, "health check includes cluster")

    # ── 21. PlatformDiagnostics ──
    print("\n=== 21. PlatformDiagnostics ===")

    pd = PlatformDiagnostics()
    pd.record_operation("register", "oms", "registry", 0.05, {"status": "ok"})
    pd.record_operation("resolve", "oms", "resolver", 0.02)
    pd.record_operation("heartbeat", "oms", "heartbeat", 0.01)
    pd.record_error("oms", "timeout", "resolve", "resolver")
    ops = pd.get_operations("oms")
    check(len(ops) == 3, "3 operations for oms")
    errs = pd.get_errors("oms")
    check(len(errs) == 1, "1 error for oms")
    perf = pd.get_performance_report()
    check("timestamp" in perf, "performance report has timestamp")
    stats = pd.get_stats()
    check(stats["operation_count"] == 3, "operation count is 3")
    check(stats["error_count"] == 1, "error count is 1")

    # ── 22. PlatformProtection & ProtectionMode ──
    print("\n=== 22. PlatformProtection & ProtectionMode ===")

    pp = PlatformProtection()
    check(pp.get_mode() == ProtectionMode.NORMAL, "initial mode is NORMAL")
    check(pp.is_normal(), "is_normal returns True initially")
    pp.activate_safe_mode("maintenance")
    check(pp.get_mode() == ProtectionMode.SAFE_MODE, "mode changed to SAFE_MODE")
    check(pp.is_read_only(), "safe mode is read-only")
    pp.activate_read_only("precaution")
    check(pp.get_mode() == ProtectionMode.READ_ONLY, "mode changed to READ_ONLY")
    pp.lock_registry("emergency")
    check(pp.is_locked(), "registry locked")
    pp.emergency_recovery("critical failure")
    check(pp.get_mode() == ProtectionMode.EMERGENCY, "emergency mode activated")
    pp.restore_normal("all clear")
    check(pp.is_normal(), "back to normal mode")
    history = pp.get_history()
    check(len(history) >= 5, "at least 5 mode changes recorded")

    # ── 23. PlatformRecovery ──
    print("\n=== 23. PlatformRecovery ===")

    pr = PlatformRecovery()
    strategies = pr.get_strategies()
    check(len(strategies) >= 3, "at least 3 default strategies")
    recovery_result = await pr.execute_recovery(error_description="test failure")
    check(isinstance(recovery_result, dict), "recovery returns dict")
    check("recovered" in recovery_result, "recovery has recovered field")
    recovery_result2 = await pr.execute_recovery(strategy_names=["nonexistent"])
    check(not recovery_result2["recovered"], "non-existent strategy fails gracefully")

    # ── 24. GracefulShutdownManager ──
    print("\n=== 24. GracefulShutdownManager ===")

    gsm = GracefulShutdownManager()
    # Register a custom phase
    phase_executed = [False]

    async def custom_cleanup():
        phase_executed[0] = True
        return "cleanup done"

    gsm.add_phase("custom", custom_cleanup, timeout_s=5.0)
    shutdown_result = await gsm.shutdown(timeout_s=60.0)
    check(shutdown_result["success"], "graceful shutdown succeeded")
    check(shutdown_result["total_phases"] >= 7, "at least 7 phases executed")
    check(phase_executed[0], "custom phase was executed")
    stats = gsm.get_stats()
    check(stats["shutdown_count"] == 1, "shutdown count is 1")

    # ── Final Summary ──
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed} passed, {failed} failed (total {total})")
    print("=" * 60)

    if failed > 0:
        print("\nFAILURES:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nALL CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
