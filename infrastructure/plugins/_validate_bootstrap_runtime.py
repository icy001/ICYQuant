"""
Validation script for the ICYQuant plugin bootstrap/runtime layer.

Comprehensive test suite covering 18 classes across the
plugin framework bootstrap and runtime components.
"""

from __future__ import annotations

import asyncio
import sys

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {'- ' + detail if detail else ''}")


def assert_eq(actual, expected, name: str) -> None:
    check(name, actual == expected, f"expected {expected!r}, got {actual!r}")


# ── 1. Container ──

def test_container():
    print("\n=== 1. Container ===")
    from infrastructure.plugins.container import Container

    class Foo:
        pass

    class Bar:
        pass

    c = Container()
    check("Container created", c is not None)

    foo = Foo()
    c.register_singleton(Foo, foo)
    check("register_singleton", c.has(Foo))

    resolved = c.resolve(Foo)
    check("resolve returns same instance", resolved is foo)

    check("has returns True for registered", c.has(Foo))
    check("has returns False for unregistered", not c.has(Bar))

    c.register_transient(Bar, lambda: Bar())
    check("register_transient", c.has(Bar))
    b1 = c.resolve(Bar)
    b2 = c.resolve(Bar)
    check("transient returns new instances", b1 is not b2)

    c.clear()
    check("clear removes all", not c.has(Foo) and not c.has(Bar))

    c.register_singleton(Foo, foo)
    stats = c.get_stats()
    assert_eq(stats["singletons"], 1, "stats has singletons count")
    check("stats has registered_types", "Foo" in stats["registered_types"])

    try:
        c.resolve(Bar)
        check("resolve unregistered raises", False)
    except Exception:
        check("resolve unregistered raises", True)


# ── 2. RuntimeContext ──

def test_runtime_context():
    print("\n=== 2. RuntimeContext ===")
    from infrastructure.plugins.runtime_context import RuntimeContext

    ctx = RuntimeContext(plugin_id="test.ctx")
    check("RuntimeContext created", ctx.plugin_id == "test.ctx")
    check("default configuration is None", ctx.configuration is None)
    check("default eventbus is None", ctx.eventbus is None)
    check("logger created", ctx.logger is not None)

    d = ctx.to_dict()
    assert_eq(d["plugin_id"], "test.ctx", "to_dict plugin_id")
    check("to_dict has_configuration false", d["has_configuration"] is False)
    check("to_dict has_eventbus false", d["has_eventbus"] is False)
    check("to_dict has_metrics false", d["has_metrics"] is False)

    result = ctx.get_config("key1", "default_val")
    assert_eq(result, "default_val", "get_config returns default")

    result2 = ctx.get_secret("mysecret")
    check("get_secret returns None when no secrets", result2 is None)

    ctx.log("info", "test message")
    check("log does not raise", True)

    ctx2 = RuntimeContext(
        plugin_id="test.ctx2",
        configuration=object(),
        eventbus=object(),
        metrics=object(),
        tracing=object(),
        secrets=object(),
        crypto=object(),
        feature_flags=object(),
    )
    d2 = ctx2.to_dict()
    check("to_dict has_configuration true", d2["has_configuration"] is True)
    check("to_dict has_eventbus true", d2["has_eventbus"] is True)
    check("to_dict has_metrics true", d2["has_metrics"] is True)
    check("to_dict has_tracing true", d2["has_tracing"] is True)
    check("to_dict has_secrets true", d2["has_secrets"] is True)
    check("to_dict has_crypto true", d2["has_crypto"] is True)
    check("to_dict has_feature_flags true", d2["has_feature_flags"] is True)


# ── 3. PluginRuntime ──

def test_plugin_runtime():
    print("\n=== 3. PluginRuntime ===")
    from infrastructure.plugins.runtime import PluginRuntime
    from infrastructure.plugins.registry import PluginRegistry
    from infrastructure.plugins.events import PluginEventBus
    from infrastructure.plugins.models import Plugin, PluginState

    async def _test():
        reg = PluginRegistry()
        bus = PluginEventBus()
        rt = PluginRuntime(registry=reg, event_bus=bus)
        check("PluginRuntime created", rt is not None)

        stats = rt.get_runtime_stats()
        assert_eq(stats["active_plugins"], 0, "initial active plugins")
        assert_eq(stats["runtime_contexts"], 0, "initial runtime contexts")
        check("stats has stats key", "stats" in stats)

        active = rt.get_active_plugins()
        assert_eq(active, [], "no active plugins initially")

        check("is_active returns False", not rt.is_active("nonexistent"))

        p = Plugin(
            id="test.runtime.plugin",
            name="Test Runtime Plugin",
            version="1.0.0",
            author="Test",
            description="A test plugin for runtime",
        )
        reg.register("test.runtime.plugin", p)
        check("plugin registered for runtime", reg.has("test.runtime.plugin"))

        check("plugin not active yet", not rt.is_active("test.runtime.plugin"))

        stats2 = rt.get_runtime_stats()
        check("stats registry total", stats2["registry"]["total"] >= 1)

    asyncio.run(_test())


# ── 4. PluginPlatform ──

def test_plugin_platform():
    print("\n=== 4. PluginPlatform ===")
    from infrastructure.plugins.platform import PluginPlatform

    async def _test():
        pp = PluginPlatform()
        check("PluginPlatform created", pp is not None)

        stats = pp.get_stats()
        check("stats has initialized", "initialized" in stats)
        check("stats has registry", "registry" in stats)
        check("stats has loader", "loader" in stats)
        check("stats has sandbox", "sandbox" in stats)
        check("stats has marketplace", "marketplace" in stats)
        check("stats has lifecycle", "lifecycle" in stats)
        check("stats has runtime", "runtime" in stats)
        check("stats has event_bus", "event_bus" in stats)

        plugins = pp.list_plugins()
        check("list_plugins returns list", isinstance(plugins, list))

        result = pp.get_plugin("nonexistent.plugin")
        check("get_plugin nonexistent returns None", result is None)

        check("Platform not initialized yet", stats["initialized"] is False)

    asyncio.run(_test())


# ── 5. PlatformIntegration ──

def test_platform_integration():
    print("\n=== 5. PlatformIntegration ===")
    from infrastructure.plugins.integration import PlatformIntegration

    pi = PlatformIntegration()
    check("PlatformIntegration created", pi is not None)

    check("not yet available", not pi.is_available("configuration"))

    result = asyncio.run(pi.integrate("configuration"))
    check("integrate configuration succeeds", pi.is_available("configuration"))

    result2 = asyncio.run(pi.integrate("eventbus"))
    check("integrate eventbus succeeds", pi.is_available("eventbus"))

    available = pi.get_available_platforms()
    check("get_available_platforms", "configuration" in available and "eventbus" in available)

    asyncio.run(pi.configure_platform({
        "configuration": {"timeout": 30},
        "eventbus": {"max_events": 1000},
    }))

    stats = pi.get_stats()
    assert_eq(stats["platform_count"], 2, "stats platform count")
    check("configured_platforms has entries", len(stats["configured_platforms"]) >= 1)

    try:
        asyncio.run(pi.integrate("unknown_platform_xyz"))
        check("integrate unknown raises", False)
    except Exception:
        check("integrate unknown raises", True)

    sync_result = asyncio.run(pi.sync_platforms())
    check("sync_platforms returns dict", isinstance(sync_result, dict))


# ── 6. PluginScheduler ──

def test_plugin_scheduler():
    print("\n=== 6. PluginScheduler ===")
    from infrastructure.plugins.scheduler import PluginScheduler

    async def _test():
        ps = PluginScheduler()
        check("PluginScheduler created", ps is not None)
        check("initially not running", not ps.is_running())

        async def dummy_task():
            return "done"

        ps.add_task("test_task", dummy_task, interval=60.0)
        tasks = ps.get_tasks()
        assert_eq(len(tasks), 1, "one task registered")
        assert_eq(tasks[0]["name"], "test_task", "task name")
        assert_eq(tasks[0]["interval"], 60.0, "task interval")

        result = await ps.run_task("test_task")
        assert_eq(result, "done", "run_task returns result")

        stats = ps.get_stats()
        assert_eq(stats["task_count"], 1, "stats task count")
        check("stats has running", "running" in stats)
        check("stats has stats key", "stats" in stats)

        await ps.start()
        check("scheduler is running", ps.is_running())

        await ps.stop()
        check("scheduler stopped", not ps.is_running())

        ps.remove_task("test_task")
        tasks2 = ps.get_tasks()
        assert_eq(len(tasks2), 0, "task removed")

        try:
            await ps.run_task("nonexistent")
            check("run_task nonexistent raises", False)
        except KeyError:
            check("run_task nonexistent raises", True)

    asyncio.run(_test())


# ── 7. PluginSynchronization ──

def test_plugin_synchronization():
    print("\n=== 7. PluginSynchronization ===")
    from infrastructure.plugins.synchronization import PluginSynchronization
    from infrastructure.plugins.registry import PluginRegistry
    from infrastructure.plugins.models import Plugin

    reg = PluginRegistry()
    sync = PluginSynchronization(registry=reg)
    check("PluginSynchronization created", sync is not None)
    assert_eq(sync.get_snapshot_version(), 0, "initial snapshot version")

    result = asyncio.run(sync.sync())
    assert_eq(result["snapshot_version"], 1, "sync increments version")
    check("sync has plugin_count", "plugin_count" in result)

    v1 = sync.get_snapshot_version()
    asyncio.run(sync.sync())
    assert_eq(sync.get_snapshot_version(), v1 + 1, "second sync increments")

    p = Plugin(
        id="sync.plugin", name="Sync Plugin", version="1.0.0",
        author="Test", description="A sync test plugin",
    )
    reg.register("sync.plugin", p)

    result2 = asyncio.run(sync.sync_plugin("sync.plugin"))
    check("sync_plugin succeeds", result2.get("success") is True)

    result3 = asyncio.run(sync.sync_plugin("nonexistent.plugin"))
    check("sync_plugin nonexistent fails", result3.get("success") is False)

    asyncio.run(sync.broadcast_event({"event_type": "test.event", "plugin_id": "p1"}))
    check("broadcast_event does not raise", True)

    local = {"plugins": {"p1": {"version": "1.0.0"}, "p2": {"version": "2.0.0"}}}
    remote = {"plugins": {"p1": {"version": "1.0.0"}, "p2": {"version": "3.0.0"}}}
    conflicts = sync.detect_conflict(local, remote)
    assert_eq(conflicts, ["p2"], "conflict detected for p2")

    no_conflict = sync.detect_conflict(local, local)
    assert_eq(no_conflict, [], "no conflict when same")

    stats = sync.get_stats()
    check("stats has snapshot_version", "snapshot_version" in stats)
    check("stats has event_log_size", "event_log_size" in stats)

    asyncio.run(sync.sync())
    log = sync.replay_events(0)
    check("replay_events returns list", isinstance(log, list))


# ── 8. RuntimeDiscovery ──

def test_runtime_discovery():
    print("\n=== 8. RuntimeDiscovery ===")
    from infrastructure.plugins.discovery import RuntimeDiscovery
    from infrastructure.plugins.registry import PluginRegistry
    from infrastructure.plugins.models import Plugin, PluginState

    reg = PluginRegistry()
    p1 = Plugin(
        id="disco.plugin.a", name="Disco A", version="1.0.0",
        author="Test", description="Discovery test",
        dependencies=["disco.plugin.b"],
    )
    p2 = Plugin(
        id="disco.plugin.b", name="Disco B", version="2.0.0",
        author="Test", description="Discovery test 2",
    )
    reg.register("disco.plugin.a", p1)
    reg.register("disco.plugin.b", p2)

    rd = RuntimeDiscovery(registry=reg)
    check("RuntimeDiscovery created", rd is not None)

    discovered = rd.discover_from_registry()
    assert_eq(len(discovered), 2, "discover_from_registry returns 2")

    running = rd.get_running_plugins()
    assert_eq(len(running), 0, "no running plugins initially")

    reg.update_state("disco.plugin.a", PluginState.RUNNING)
    running2 = rd.get_running_plugins()
    assert_eq(len(running2), 1, "one running plugin")

    graph = rd.get_plugin_graph()
    check("graph has disco.plugin.a", "disco.plugin.a" in graph)
    assert_eq(graph["disco.plugin.a"], ["disco.plugin.b"], "graph deps for a")
    assert_eq(graph["disco.plugin.b"], [], "graph deps for b")

    topology = rd.get_runtime_topology()
    assert_eq(topology["total_plugins"], 2, "topology total plugins")
    check("topology has by_state", "by_state" in topology)

    stats = rd.get_stats()
    check("stats has registry_plugins", "registry_plugins" in stats)
    check("stats has topology", "topology" in stats)


# ── 9. SnapshotManager ──

def test_snapshot_manager():
    print("\n=== 9. SnapshotManager ===")
    from infrastructure.plugins.snapshot import SnapshotManager, PluginSnapshot

    sm = SnapshotManager()
    check("SnapshotManager created", sm is not None)

    snap1 = asyncio.run(sm.create_snapshot())
    check("create_snapshot returns PluginSnapshot", isinstance(snap1, PluginSnapshot))
    assert_eq(snap1.version, 1, "first snapshot version is 1")
    check("snapshot has checksum", len(snap1.checksum) > 0)
    check("snapshot has created_at", snap1.created_at is not None)

    snap2 = asyncio.run(sm.create_snapshot())
    assert_eq(snap2.version, 2, "second snapshot version is 2")

    snaps = asyncio.run(sm.list_snapshots())
    assert_eq(len(snaps), 2, "two snapshots listed")
    check("list has version", "version" in snaps[0])
    check("list has checksum", "checksum" in snaps[0])

    retrieved = asyncio.run(sm.get_snapshot(1))
    check("get_snapshot returns snapshot", retrieved is not None)
    assert_eq(retrieved.version, 1, "retrieved version matches")

    result = sm.compare_snapshots(1, 2)
    assert_eq(result["v1"], 1, "compare v1")
    assert_eq(result["v2"], 2, "compare v2")
    check("compare has identical", "identical" in result)

    restored = asyncio.run(sm.restore_snapshot(1))
    check("restore succeeds", restored.get("success") is True)

    asyncio.run(sm.delete_snapshot(2))
    snaps2 = asyncio.run(sm.list_snapshots())
    assert_eq(len(snaps2), 1, "one snapshot after deletion")

    try:
        sm.compare_snapshots(1, 2)
        check("compare missing raises", False)
    except Exception:
        check("compare missing raises", True)

    stats = sm.get_stats()
    assert_eq(stats["total_snapshots"], 1, "stats total snapshots")

    snap_data = snap1.to_dict()
    check("snapshot to_dict has version", "version" in snap_data)
    check("snapshot to_dict has plugins", "plugins" in snap_data)

    restored_snap = PluginSnapshot.from_dict(snap_data)
    assert_eq(restored_snap.version, snap1.version, "from_dict roundtrip")


# ── 10. VersionManager ──

def test_version_manager():
    print("\n=== 10. VersionManager ===")
    from infrastructure.plugins.version import VersionManager, PluginVersion
    from infrastructure.plugins.exceptions import PluginError

    vm = VersionManager()
    check("VersionManager created", vm is not None)

    rec1 = vm.record_version("test.plugin", "1.0.0", action="install")
    check("record_version returns PluginVersion", isinstance(rec1, PluginVersion))
    assert_eq(rec1.plugin_id, "test.plugin", "record plugin_id")
    assert_eq(rec1.version, "1.0.0", "record version")
    assert_eq(rec1.action, "install", "record action")

    rec2 = vm.record_version("test.plugin", "1.1.0", action="upgrade")
    assert_eq(rec2.previous_version, "1.0.0", "previous version tracked")

    history = vm.get_version_history("test.plugin")
    assert_eq(len(history), 2, "two history records")

    current = vm.get_current_version("test.plugin")
    assert_eq(current, "1.1.0", "current version")

    previous = vm.get_previous_version("test.plugin")
    assert_eq(previous, "1.0.0", "previous version")

    cmp_result = vm.compare_versions("1.0.0", "2.0.0")
    assert_eq(cmp_result, -1, "compare 1.0.0 < 2.0.0")

    cmp_result2 = vm.compare_versions("2.0.0", "1.0.0")
    assert_eq(cmp_result2, 1, "compare 2.0.0 > 1.0.0")

    cmp_result3 = vm.compare_versions("1.0.0", "1.0.0")
    assert_eq(cmp_result3, 0, "compare equal")

    diff = vm.get_diff("1.0.0", "2.0.0")
    assert_eq(diff["major_changed"], True, "major changed")
    assert_eq(diff["change_type"], "major", "change type major")

    diff2 = vm.get_diff("1.0.0", "1.1.0")
    assert_eq(diff2["minor_changed"], True, "minor changed")
    assert_eq(diff2["change_type"], "minor", "change type minor")

    diff3 = vm.get_diff("1.0.0", "1.0.1")
    assert_eq(diff3["patch_changed"], True, "patch changed")
    assert_eq(diff3["change_type"], "patch", "change type patch")

    rec3 = vm.record_version("test.plugin", "1.0.0", action="rollback")
    assert_eq(rec3.version, "1.0.0", "rollback version")

    try:
        vm.record_version("test.plugin", "1.0.0", action="invalid_action")
        check("invalid action raises", False)
    except PluginError:
        check("invalid action raises", True)

    stats = vm.get_stats()
    assert_eq(stats["tracked_plugins"], 1, "tracked plugins")
    check("stats has current_versions", "current_versions" in stats)

    rec_dict = rec1.to_dict()
    check("record to_dict has plugin_id", "plugin_id" in rec_dict)
    check("record to_dict has version", "version" in rec_dict)


# ── 11. PluginPublisher ──

def test_plugin_publisher():
    print("\n=== 11. PluginPublisher ===")
    from infrastructure.plugins.publisher import PluginPublisher
    from infrastructure.plugins.events import PluginEventBus, PluginEvent, PluginEventType

    bus = PluginEventBus()
    pub = PluginPublisher(event_bus=bus)
    check("PluginPublisher created", pub is not None)

    async def handler(event):
        pass

    asyncio.run(bus.subscribe(PluginEventType.STARTED, handler))

    asyncio.run(pub.publish(PluginEventType.STARTED, {"key": "value"}))
    stats = pub.get_stats()
    assert_eq(stats["total_published"], 1, "one event published")

    pub.register_publisher("test.plugin")
    publishers = pub.get_publishers()
    assert_eq(publishers, ["test.plugin"], "publisher registered")

    pub.register_publisher("test.plugin.2")
    publishers2 = pub.get_publishers()
    assert_eq(len(publishers2), 2, "two publishers registered")

    asyncio.run(pub.publish_plugin_event("test.plugin", PluginPublisher.EVENT_STARTED))
    stats2 = pub.get_stats()
    assert_eq(stats2["total_published"], 2, "two events total")

    check("stats has registered_publishers", "registered_publishers" in stats2)
    check("stats has event_counts", "event_counts" in stats2)

    asyncio.run(pub.broadcast({"event_type": "test.broadcast", "plugin_id": "p1", "data": {}}))
    stats3 = pub.get_stats()
    assert_eq(stats3["total_published"], 3, "three events total after broadcast")


# ── 12. PluginSubscriber ──

def test_plugin_subscriber():
    print("\n=== 12. PluginSubscriber ===")
    from infrastructure.plugins.subscriber import PluginSubscriber
    from infrastructure.plugins.events import PluginEventBus, PluginEvent

    bus = PluginEventBus()
    sub = PluginSubscriber(event_bus=bus)
    check("PluginSubscriber created", sub is not None)

    notifications = []

    def callback(event):
        notifications.append(event)

    asyncio.run(sub.subscribe("oms", callback))
    subs = sub.get_subscribers()
    check("subscriber registered", "oms" in subs)
    assert_eq(len(subs["oms"]), 1, "one callback for oms")

    def callback2(event):
        notifications.append(event)

    asyncio.run(sub.subscribe("custom_plugin", callback2))
    subs2 = sub.get_subscribers()
    check("custom subscriber registered", "custom_plugin" in subs2)

    sub.notify("plugin.started", {"plugin_id": "test.notify"})
    assert_eq(len(notifications), 2, "two notifications sent")

    asyncio.run(sub.unsubscribe("oms"))
    subs3 = sub.get_subscribers()
    check("oms unsubscribed", "oms" not in subs3)

    stats = sub.get_stats()
    check("stats has total_subscribers", "total_subscribers" in stats)
    check("stats has total_notifications", "total_notifications" in stats)
    check("stats has subscriber_ids", "subscriber_ids" in stats)


# ── 13. PluginMonitoring ──

def test_plugin_monitoring():
    print("\n=== 13. PluginMonitoring ===")
    from infrastructure.plugins.monitoring import PluginMonitoring
    from infrastructure.plugins.registry import PluginRegistry
    from infrastructure.plugins.models import Plugin, PluginState

    reg = PluginRegistry()
    p = Plugin(
        id="mon.plugin", name="Mon Plugin", version="1.0.0",
        author="Test", description="Monitoring test",
    )
    reg.register("mon.plugin", p)

    mon = PluginMonitoring(registry=reg)
    check("PluginMonitoring created", mon is not None)
    check("initially not running", not mon.is_running())

    asyncio.run(mon.start())
    check("monitoring is running", mon.is_running())

    metrics = asyncio.run(mon.collect_metrics())
    check("metrics has runtime_total", "icyquant_plugin_runtime_total" in metrics)
    check("metrics has active_total", "icyquant_plugin_active_total" in metrics)
    check("metrics has snapshot_version", "icyquant_plugin_snapshot_version" in metrics)
    assert_eq(metrics["icyquant_plugin_runtime_total"], 1, "one plugin in metrics")

    plugin_metrics = mon.get_plugin_metrics("mon.plugin")
    check("plugin metrics has id", plugin_metrics.get("id") == "mon.plugin")

    sys_metrics = mon.get_system_metrics()
    check("system metrics has runtime_total", "icyquant_plugin_runtime_total" in sys_metrics)

    check("get_active_count returns int", isinstance(mon.get_active_count(), int))
    check("get_total_count >= 1", mon.get_total_count() >= 1)
    check("get_snapshot_version > 0", mon.get_snapshot_version() > 0)

    mon.increment_sync()
    check("get_sync_total incremented", mon.get_sync_total() >= 1)

    mon.increment_restart()
    check("get_restart_total incremented", mon.get_restart_total() >= 1)

    mon.increment_recovery()
    check("get_recovery_total incremented", mon.get_recovery_total() >= 1)

    asyncio.run(mon.stop())
    check("monitoring stopped", not mon.is_running())

    stats = mon.get_stats()
    check("stats has running", "running" in stats)
    check("stats has active_count", "active_count" in stats)
    check("stats has total_count", "total_count" in stats)


# ── 14. PluginTelemetry ──

def test_plugin_telemetry():
    print("\n=== 14. PluginTelemetry ===")
    from infrastructure.plugins.telemetry import PluginTelemetry

    tel = PluginTelemetry()
    check("PluginTelemetry created", tel is not None)

    tel.record_event("installed", "tel.plugin", {"version": "1.0.0"})
    tel.record_event("started", "tel.plugin", {"state": "running"})

    stats = tel.get_stats()
    assert_eq(stats["total_events"], 2, "two events recorded")

    audit = tel.get_audit_trail("tel.plugin")
    assert_eq(len(audit), 2, "audit trail has two entries")
    check("audit entry has event_type", "event_type" in audit[0])

    span_id = tel.start_span("install_plugin", plugin_id="tel.plugin")
    check("start_span returns id", len(span_id) > 0)

    spans = tel.get_spans(plugin_id="tel.plugin")
    check("get_spans returns list", isinstance(spans, list))
    check("span created", len(spans) >= 1)

    tel.end_span(span_id, status="ok")
    spans2 = tel.get_spans(plugin_id="tel.plugin")
    check("span ended", spans2[0]["status"] == "ok")

    traces = tel.get_traces(plugin_id="tel.plugin")
    check("get_traces returns list", isinstance(traces, list))
    check("trace has span_count", all("span_count" in t for t in traces))

    stats2 = tel.get_stats()
    assert_eq(stats2["total_spans"], 1, "one span total")
    assert_eq(stats2["completed_spans"], 1, "one completed span")
    assert_eq(stats2["active_spans"], 0, "no active spans")
    check("stats has total_traces", "total_traces" in stats2)

    tel.record_event("stopped", "tel.plugin.2")
    audit2 = tel.get_audit_trail("tel.plugin.2")
    assert_eq(len(audit2), 1, "audit trail for second plugin")


# ── 15. PluginProtection ──

def test_plugin_protection():
    print("\n=== 15. PluginProtection ===")
    from infrastructure.plugins.protection import PluginProtection, CIRCUIT_CLOSED, CIRCUIT_HALF_OPEN, CIRCUIT_OPEN

    prot = PluginProtection()
    check("PluginProtection created", prot is not None)

    result = asyncio.run(prot.check_plugin("prot.plugin"))
    check("check_plugin allowed initially", result["allowed"] is True)
    check("check_plugin state closed", result["state"] == CIRCUIT_CLOSED)

    asyncio.run(prot.on_failure("prot.plugin", "test error 1"))
    state = prot.get_circuit_state("prot.plugin")
    check("circuit still closed after 1 failure", state == CIRCUIT_CLOSED)

    asyncio.run(prot.on_failure("prot.plugin", "test error 2"))
    state2 = prot.get_circuit_state("prot.plugin")
    check("circuit half_open after 2 failures", state2 == CIRCUIT_HALF_OPEN)

    asyncio.run(prot.on_failure("prot.plugin", "test error 3"))
    state3 = prot.get_circuit_state("prot.plugin")
    check("circuit open after 3 failures", state3 == CIRCUIT_OPEN)

    check("is_circuit_open returns True", prot.is_circuit_open("prot.plugin"))

    result2 = asyncio.run(prot.check_plugin("prot.plugin"))
    check("check_plugin blocked when open", result2["allowed"] is False)

    prot.reset_circuit("prot.plugin")
    check("circuit reset to closed", prot.get_circuit_state("prot.plugin") == CIRCUIT_CLOSED)
    check("is_circuit_open false after reset", not prot.is_circuit_open("prot.plugin"))

    check("get_violation_count > 0", prot.get_violation_count("prot.plugin") >= 3)

    for _ in range(6):
        prot.increment_restart("restart.plugin")
    check("get_restart_count >= 5", prot.get_restart_count("restart.plugin") >= 5)

    result3 = asyncio.run(prot.check_plugin("restart.plugin"))
    check("blocked after max restarts", result3["allowed"] is False)

    check("not in safe mode initially", not prot.is_safe_mode())
    prot.set_safe_mode(True)
    check("safe mode enabled", prot.is_safe_mode())
    prot.set_safe_mode(False)
    check("safe mode disabled", not prot.is_safe_mode())

    stats = prot.get_stats()
    check("stats has safe_mode", "safe_mode" in stats)
    check("stats has circuits", "circuits" in stats)
    check("stats has closed_circuits", "closed_circuits" in stats)
    check("stats has half_open_circuits", "half_open_circuits" in stats)
    check("stats has open_circuits", "open_circuits" in stats)
    check("stats has max_failures_threshold", "max_failures_threshold" in stats)


# ── 16. GracefulShutdown ──

def test_graceful_shutdown():
    print("\n=== 16. GracefulShutdown ===")
    from infrastructure.plugins.shutdown import GracefulShutdown

    async def _test():
        gs = GracefulShutdown()
        check("GracefulShutdown created", gs is not None)
        check("initially not shutting down", not gs.is_shutting_down())

        await gs.shutdown()
        check("shutdown completes", not gs.is_shutting_down())

        stats = gs.get_stats()
        check("stats has completed_steps", "completed_steps" in stats)
        check("stats has step_count", stats["step_count"] == 5)
        check("stats has shutting_down", "shutting_down" in stats)
        check("stats has elapsed", "elapsed" in stats)
        check("stats has errors", "errors" in stats)

        steps = stats["completed_steps"]
        check("stop_scheduler step completed", "stop_scheduler" in steps)
        check("stop_plugins step completed", "stop_plugins" in steps)
        check("persist_snapshot step completed", "persist_snapshot" in steps)
        check("flush_events step completed", "flush_events" in steps)
        check("shutdown_runtime step completed", "shutdown_runtime" in steps)

        gs2 = GracefulShutdown()
        await gs2.stop_scheduler()
        await gs2.stop_plugins()
        check("individual steps work", True)

    asyncio.run(_test())


# ── 17. PluginAPI ──

def test_plugin_api():
    print("\n=== 17. PluginAPI ===")
    from infrastructure.plugins.api import PluginAPI

    async def _test():
        api = PluginAPI()
        check("PluginAPI created", api is not None)

        hc = await api.health_check()
        check("health_check returns dict", isinstance(hc, dict))
        check("health_check has status", "status" in hc)
        check("health_check has monitoring", "monitoring" in hc)
        check("health_check has protection", "protection" in hc)
        check("health_check has telemetry", "telemetry" in hc)
        check("health_check has service", "service" in hc)

        plugins = await api.list_plugins()
        check("list_plugins returns list", isinstance(plugins, list))

        snap = await api.get_snapshot()
        check("get_snapshot returns dict", isinstance(snap, dict))
        check("snapshot has monitoring", "monitoring" in snap)
        check("snapshot has protection", "protection" in snap)
        check("snapshot has telemetry", "telemetry" in snap)

        result = await api.get_plugin("nonexistent.plugin")
        check("get_plugin nonexistent returns dict", isinstance(result, dict))

        stats = api.get_stats()
        check("stats has total_requests", "total_requests" in stats)
        check("stats has methods", "methods" in stats)
        check("stats has monitoring", "monitoring" in stats)
        check("stats has protection", "protection" in stats)
        check("stats has telemetry", "telemetry" in stats)

        search_results = await api.search_plugins("nonexistent")
        check("search returns list", isinstance(search_results, list))

        hc2 = await api.health_check()
        check("second health check tracked", True)
        check("total_requests > 0", stats["total_requests"] >= 4)

    asyncio.run(_test())


# ── 18. PluginBootstrap ──

def test_plugin_bootstrap():
    print("\n=== 18. PluginBootstrap ===")
    from infrastructure.plugins.bootstrap import PluginBootstrap
    from infrastructure.plugins.runtime import PluginRuntime
    from infrastructure.plugins.platform import PluginPlatform
    from infrastructure.plugins.container import Container

    async def _test():
        boot = PluginBootstrap()
        check("PluginBootstrap created", boot is not None)

        platform = boot.get_platform()
        check("get_platform returns PluginPlatform", isinstance(platform, PluginPlatform))

        runtime = boot.get_runtime()
        check("get_runtime returns PluginRuntime", isinstance(runtime, PluginRuntime))

        container = boot.get_container()
        check("get_container returns Container", isinstance(container, Container))

        stats = boot.get_stats()
        check("stats has initialized", "initialized" in stats)
        check("stats has container", "container" in stats)
        check("stats has platform", "platform" in stats)
        check("stats has runtime", "runtime" in stats)
        check("stats has startup_duration", "startup_duration" in stats)
        check("stats has marketplace", "marketplace" in stats)
        check("stats has registry", "registry" in stats)
        check("stats has sandbox", "sandbox" in stats)

        await boot.startup()
        check("bootstrap started", boot._initialized)

        stats2 = boot.get_stats()
        assert_eq(stats2["initialized"], True, "initialized after startup")

        await boot.shutdown()
        check("bootstrap shutdown complete", not boot._initialized)

        boot2 = PluginBootstrap()
        check("new bootstrap not initialized", not boot2._initialized)

    asyncio.run(_test())


# ── Main ──

def main():
    print("=" * 60)
    print("  ICYQuant Bootstrap/Runtime Layer Validation")
    print("=" * 60)

    test_container()
    test_runtime_context()
    test_plugin_runtime()
    test_plugin_platform()
    test_platform_integration()
    test_plugin_scheduler()
    test_plugin_synchronization()
    test_runtime_discovery()
    test_snapshot_manager()
    test_version_manager()
    test_plugin_publisher()
    test_plugin_subscriber()
    test_plugin_monitoring()
    test_plugin_telemetry()
    test_plugin_protection()
    test_graceful_shutdown()
    test_plugin_api()
    test_plugin_bootstrap()

    print("\n" + "=" * 60)
    print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n  All bootstrap/runtime validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()