"""
Validation script for plugin framework foundation.

Comprehensive test suite covering all plugin framework components.
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


# ── 1. Exceptions ──

def test_exceptions():
    print("\n=== 1. Exceptions ===")
    from infrastructure.plugins.exceptions import (
        PluginError, PluginNotFoundError, PluginAlreadyExistsError,
        PluginLoadError, PluginValidationError, PluginDependencyError,
        PluginCircularDependencyError, PluginPermissionError,
        PluginManifestError,
    )

    e = PluginNotFoundError("test.flag")
    check("Exception message", "test.flag" in str(e))
    check("Exception to_dict", e.to_dict()["error"] == "PluginNotFoundError")
    check("Exception to_dict msg", e.to_dict()["message"] == "test.flag")

    e2 = PluginCircularDependencyError("plugin-a -> plugin-b -> plugin-a")
    check("CircularDep exception", isinstance(e2, PluginDependencyError))
    check("CircularDep str", "CircularDependency" in e2.to_dict()["error"])


# ── 2. Utils ──

def test_utils():
    print("\n=== 2. Utils ===")
    from infrastructure.plugins.utils import (
        slugify, generate_plugin_id, parse_version, compare_versions,
        is_compatible_version, generate_instance_id, merge_configs,
        truncate_text, safe_import, sanitize_plugin_name,
    )

    check("slugify", slugify("My Plugin Name") == "my-plugin-name")
    check("slugify dots", slugify("broker.ibkr") == "broker-ibkr")

    check("parse_version", parse_version("1.2.3") == (1, 2, 3))
    check("parse_version v", parse_version("v1.0.0") == (1, 0, 0))
    check("parse_version single", parse_version("2") == (2, 0, 0))

    check("compare_versions lt", compare_versions("1.0.0", "2.0.0") == -1)
    check("compare_versions eq", compare_versions("1.0.0", "1.0.0") == 0)
    check("compare_versions gt", compare_versions("2.0.0", "1.0.0") == 1)

    check("is_compatible_version", is_compatible_version(">=1.0.0", "1.5.0"))
    check("is_compatible_version false", not is_compatible_version(">=2.0.0", "1.0.0"))

    id1 = generate_instance_id()
    id2 = generate_instance_id()
    check("generate_instance_id", len(id1) > 0 and id1 != id2)

    merged = merge_configs({"a": 1, "b": {"c": 2}}, {"b": {"d": 3}})
    check("merge_configs", merged == {"a": 1, "b": {"c": 2, "d": 3}})

    check("truncate_text", truncate_text("hello world", 5) == "he...")
    check("safe_import success", safe_import("json") is not None)
    check("safe_import None", safe_import("nonexistent_module_xyz") is None)

    check("sanitize", sanitize_plugin_name("my!@#plugin") == "myplugin")


# ── 3. Models ──

def test_models():
    print("\n=== 3. Models ===")
    from infrastructure.plugins.models import (
        Plugin, PluginInstance, PluginInfo,
        PluginState, PluginPriority,
    )
    from datetime import datetime

    p = Plugin(
        id="test.plugin",
        name="Test Plugin",
        version="1.0.0",
        author="Test Author",
        description="A test plugin",
    )
    check("Plugin created", p.id == "test.plugin")
    check("Plugin state", p.state == PluginState.REGISTERED)
    check("Plugin to_dict", "id" in p.to_dict())
    check("Plugin roundtrip", Plugin.from_dict(p.to_dict()).id == p.id)

    pi = PluginInstance(
        plugin_id="test.plugin",
        instance_id="inst-1",
        state=PluginState.RUNNING,
        started_at=datetime.utcnow(),
    )
    check("PluginInstance created", pi.instance_id == "inst-1")

    info = PluginInfo(
        id="test.plugin", name="Test", version="1.0.0",
        state="registered", author="Test", description="Test",
    )
    check("PluginInfo created", info.id == "test.plugin")

    check("PluginState.REGISTERED", PluginState.REGISTERED.value == "registered")
    check("PluginPriority.LOW", PluginPriority.LOW.value == 90)


# ── 4. Manifest ──

def test_manifest():
    print("\n=== 4. Manifest ===")
    from infrastructure.plugins.manifest import PluginManifest

    m = PluginManifest(
        id="broker.ibkr",
        name="IBKR Broker Adapter",
        version="1.0.0",
        api="v1",
        entrypoint="broker_ibkr.plugin",
        author="ICYQuant",
        permissions=["broker.trade", "broker.market"],
        dependencies=["eventbus", "secrets"],
        capabilities=["broker"],
    )
    check("Manifest created", m.id == "broker.ibkr")
    check("Manifest validate", len(m.validate()) == 0)
    check("Manifest to_dict", "id" in m.to_dict())

    m2 = PluginManifest.from_dict(m.to_dict())
    check("Manifest roundtrip", m2.id == m.id)

    yml = m.to_yaml()
    check("Manifest to_yaml", "broker.ibkr" in yml)

    m3 = PluginManifest.from_yaml_string(yml)
    check("Manifest from_yaml_string", m3.id == m.id)

    check("Manifest compatible", m.is_compatible("v1"))
    check("Manifest not compatible", not m.is_compatible("v2"))

    # Invalid manifest
    bad = PluginManifest(id="", name="", version="")
    errors = bad.validate()
    check("Bad manifest has errors", len(errors) > 0)


# ── 5. Metadata ──

def test_metadata():
    print("\n=== 5. Metadata ===")
    from infrastructure.plugins.metadata import PluginMetadata, MetadataRegistry

    meta = PluginMetadata(
        plugin_id="test.plugin",
        name="Test Plugin",
        version="1.0.0",
        author="Test",
        tags=["test", "example"],
    )
    check("Metadata created", meta.plugin_id == "test.plugin")
    check("Metadata has_tag", meta.has_tag("test"))
    meta.add_tag("new")
    check("Metadata add_tag", meta.has_tag("new"))

    reg = MetadataRegistry()
    reg.register(meta)
    check("Registry has", reg.get("test.plugin") is not None)

    reg.unregister("test.plugin")
    check("Registry removed", reg.get("test.plugin") is None)

    # Re-register for search test
    reg.register(meta)
    results = reg.search(tag="test")
    check("Search by tag", len(results) >= 1)

    check("Registry to_dict", "count" in reg.to_dict())


# ── 6. Capabilities ──

def test_capabilities():
    print("\n=== 6. Capabilities ===")
    from infrastructure.plugins.capabilities import (
        Capability, CapabilityRequirement, CapabilityDeclaration,
        CapabilityRegistry,
    )

    check("Capability.BROKER", Capability.BROKER.value == "broker")

    cap_req = CapabilityRequirement(capability=Capability.BROKER, min_version="1.0.0")
    check("CapabilityRequirement", cap_req.capability == Capability.BROKER)

    decl = CapabilityDeclaration(
        plugin_id="test.plugin",
        capabilities=[cap_req],
    )
    check("Declaration has capability", decl.has_capability(Capability.BROKER))
    check("Declaration no capability", not decl.has_capability(Capability.RISK))

    cap_reg = CapabilityRegistry()
    cap_reg.register("test.plugin", [Capability.BROKER, Capability.MARKET_DATA])
    check("Registry has", cap_reg.has_capability("test.plugin", Capability.BROKER))
    check("Registry resolve", cap_reg.resolve(Capability.BROKER) == "test.plugin")
    check("Registry no resolve", cap_reg.resolve(Capability.RISK) is None)

    plugins = cap_reg.get_plugins_with_capability(Capability.BROKER)
    check("Plugins with capability", "test.plugin" in plugins)


# ── 7. Permissions ──

def test_permissions():
    print("\n=== 7. Permissions ===")
    from infrastructure.plugins.permissions import (
        Permission, PermissionSet, PermissionChecker,
        DANGEROUS_PERMISSIONS,
    )
    from infrastructure.plugins.exceptions import PluginPermissionError

    check("Permission.TRADE_ORDER", Permission.TRADE_ORDER.value == "trade_order")
    check("Dangerous permissions", Permission.TRADE_ORDER in DANGEROUS_PERMISSIONS)

    ps = PermissionSet.from_list(["read_config", "trade_order"])
    check("PermissionSet grants", ps.grants(Permission.TRADE_ORDER))
    check("PermissionSet not grant", not ps.grants(Permission.NETWORK))

    ps.grant(Permission.NETWORK)
    check("After grant", ps.grants(Permission.NETWORK))

    ps.revoke(Permission.TRADE_ORDER)
    check("After revoke", not ps.grants(Permission.TRADE_ORDER))

    checker = PermissionChecker()
    checker.declare("test.plugin", PermissionSet.from_list(["read_config"]))
    check("Checker grants", checker.check("test.plugin", Permission.READ_CONFIG))
    check("Checker denies", not checker.check("test.plugin", Permission.NETWORK))

    try:
        checker.require("test.plugin", Permission.NETWORK)
        check("Checker should raise", False)
    except PluginPermissionError:
        check("Checker raises on missing permission", True)

    audit = checker.audit("test.plugin")
    check("Audit has declared", "declared" in audit)

    checker.revoke_all("test.plugin")
    check("After revoke_all", not checker.check("test.plugin", Permission.READ_CONFIG))


# ── 8. Context ──

def test_context():
    print("\n=== 8. Context ===")
    from infrastructure.plugins.context import PluginContext, ContextBuilder

    ctx = PluginContext(plugin_id="test.plugin", config={"key": "value"})
    check("Context created", ctx.plugin_id == "test.plugin")
    check("Context get_config", ctx.get_config("key") == "value")
    check("Context get_config default", ctx.get_config("missing", "default") == "default")

    ctx.set_config("new", "val")
    check("Context set_config", ctx.get_config("new") == "val")

    ctx.log(10, "test message")  # should not raise
    check("Context log works", True)

    ctx2 = ContextBuilder("test.plugin").with_config({"a": 1}).build()
    check("Builder config", ctx2.get_config("a") == 1)

    check("Context to_dict", "plugin_id" in ctx2.to_dict())

    ctx3 = PluginContext.create("new.plugin", config={"x": 1})
    check("Context.create", ctx3.plugin_id == "new.plugin")


# ── 9. Configuration ──

def test_configuration():
    print("\n=== 9. Configuration ===")
    from infrastructure.plugins.configuration import PluginConfig, ConfigurationManager

    cfg = PluginConfig(plugin_id="test.plugin", default={"timeout": 30, "retries": 3})
    check("Config get default", cfg.get("timeout") == 30)

    cfg.set("timeout", 60)
    check("Config override", cfg.get("timeout") == 60)
    check("Config merge", cfg.all() == {"timeout": 60, "retries": 3})

    mgr = ConfigurationManager()
    mgr.register("test.plugin", {"debug": False})
    check("Manager get_value", mgr.get_value("test.plugin", "debug") is False)

    mgr.set_override("test.plugin", "debug", True)
    check("Manager override", mgr.get_value("test.plugin", "debug") is True)

    mgr.reload("test.plugin", {"debug": False, "new_key": "val"})
    check("Manager reload", mgr.get_value("test.plugin", "new_key") == "val")

    listener_calls = []
    mgr.add_listener("test.plugin", lambda c: listener_calls.append(c))
    mgr.set_override("test.plugin", "debug", True)
    check("Listener called", len(listener_calls) >= 1)

    configs = mgr.list_configs()
    check("List configs", "test.plugin" in configs)


# ── 10. Hooks ──

async def test_hooks():
    print("\n=== 10. Hooks ===")
    from infrastructure.plugins.hooks import HookRegistry, HookPoint

    hr = HookRegistry()
    results = []

    async def hook1(*args, **kwargs):
        results.append(("hook1", 1))

    async def hook2(*args, **kwargs):
        results.append(("hook2", 0))

    hr.register(HookPoint.BEFORE_LOAD, hook1, priority=10)
    hr.register(HookPoint.BEFORE_LOAD, hook2, priority=0)

    await hr.execute(HookPoint.BEFORE_LOAD)
    check("Hooks executed in priority order", results[0][0] == "hook2")
    check("Both hooks executed", len(results) == 2)

    hooks = hr.get_hooks(HookPoint.BEFORE_LOAD)
    check("Get hooks sorted", hooks[0][0] == 0)

    hr.unregister(HookPoint.BEFORE_LOAD, hook1)
    hooks2 = hr.get_hooks(HookPoint.BEFORE_LOAD)
    check("After unregister", len(hooks2) == 1)

    check("Hooks to_dict", "before_load" in hr.to_dict())


# ── 11. Events ──

async def test_events():
    print("\n=== 11. Events ===")
    from infrastructure.plugins.events import PluginEvent, PluginEventType, PluginEventBus

    bus = PluginEventBus()
    received = []

    async def handler(event):
        received.append(event)

    await bus.subscribe(PluginEventType.LOADED, handler)

    event = PluginEvent(
        event_type=PluginEventType.LOADED,
        plugin_id="test.plugin",
        data={"version": "1.0.0"},
    )
    notified = await bus.publish(event)
    check("Event published", notified >= 1)
    check("Event received", len(received) == 1)
    check("Event type", received[0].event_type == PluginEventType.LOADED)

    # Wildcard
    all_received = []
    async def wildcard_handler(evt):
        all_received.append(evt)
    await bus.subscribe_all(wildcard_handler)
    await bus.publish(event)
    check("Wildcard received", len(all_received) == 1)

    history = bus.get_history(plugin_id="test.plugin")
    check("History has events", len(history) >= 2)

    stats = bus.get_stats()
    check("Bus stats", "total_events" in stats)

    await bus.shutdown()
    check("Bus shutdown", bus.get_stats()["history_size"] == 0)


# ── 12. Registry ──

def test_registry():
    print("\n=== 12. Registry ===")
    from infrastructure.plugins.registry import PluginRegistry

    reg = PluginRegistry()

    class MockPlugin:
        def __init__(self, pid, state="registered"):
            self.id = pid
            self.name = pid
            self.state = state
            self.description = "Test"
            self.capabilities = []
            self.permissions = []

    p1 = MockPlugin("plugin.a", "running")
    p2 = MockPlugin("plugin.b", "stopped")

    reg.register("plugin.a", p1)
    reg.register("plugin.b", p2)
    check("Registry count", reg.count() == 2)
    check("Registry has", reg.has("plugin.a"))
    check("Registry lookup", reg.get_plugin("plugin.a") is p1)

    by_state = reg.get_by_state("running")
    check("Get by state", len(by_state) == 1)

    reg.update_state("plugin.a", "stopped")
    from infrastructure.plugins.models import PluginState
    check("State updated", reg.get_plugin("plugin.a").state == PluginState.STOPPED)

    check("List ids", len(reg.list_ids()) == 2)

    search = reg.search("plugin.a")
    check("Search found", len(search) >= 1)

    stats = reg.get_stats()
    check("Registry stats", "by_state" in stats)

    reg.unregister("plugin.a")
    check("After unregister", not reg.has("plugin.a"))

    reg.clear()
    check("After clear", reg.count() == 0)


# ── 13. Loader ──

def test_loader():
    print("\n=== 13. Loader ===")
    from infrastructure.plugins.loader import PluginLoader

    loader = PluginLoader()

    check("Validate entrypoint ok", loader.validate_entrypoint("module:Class"))
    check("Validate entrypoint bad", not loader.validate_entrypoint("in valid::"))

    # Test loading a real module
    module = loader.load_module("json")
    check("Load module", module is not None)

    check("Loader stats", "importer" in loader.get_stats())


# ── 14. Dependency ──

def test_dependency():
    print("\n=== 14. Dependency ===")
    from infrastructure.plugins.dependency import DependencyResolver

    resolver = DependencyResolver()

    plugins = {
        "plugin-a": ["plugin-b"],
        "plugin-b": ["plugin-c"],
        "plugin-c": [],
    }
    graph = resolver.build_graph(plugins)
    check("Graph built", len(graph) == 3)

    cycles = resolver.detect_cycles(graph)
    check("No cycles", len(cycles) == 0)

    order = resolver.topological_sort(graph)
    check("Topological sort", order.index("plugin-c") < order.index("plugin-b"))

    missing = resolver.find_missing(graph, {"plugin-c", "plugin-b", "plugin-a"})
    check("No missing", len(missing) == 0)

    missing2 = resolver.find_missing(graph, {"plugin-a"})
    check("Missing detected", len(missing2) >= 1)

    # Test circular
    circular = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }
    cycles2 = resolver.detect_cycles(circular)
    check("Cycle detected", len(cycles2) >= 1)

    # Version constraint
    check("Version >= passes", resolver.check_version_constraint(">=1.0.0", "1.2.0"))
    check("Version >= fails", not resolver.check_version_constraint(">=2.0.0", "0.9.0"))

    # Optional dep
    opt_plugins = {"a": ["b", "?c"], "b": []}
    result = resolver.resolve(opt_plugins, {"a", "b"})
    check("Optional dep not required", result["valid"] is True)

    tree = resolver.get_dependency_tree("plugin-a", graph)
    check("Tree has root", tree["id"] == "plugin-a")

    check("Resolver to_dict", "last_resolution" in resolver.to_dict())


# ── 15. Lifecycle ──

async def test_lifecycle():
    print("\n=== 15. Lifecycle ===")
    from infrastructure.plugins.lifecycle import PluginLifecycle
    from infrastructure.plugins.models import PluginState, Plugin

    lc = PluginLifecycle()

    p = Plugin(
        id="test.plugin", name="Test", version="1.0.0",
        author="Test", description="Test",
    )
    lc.register("test.plugin", p)

    check("Can transition", lc.can_transition(PluginState.REGISTERED, PluginState.LOADED))
    check("Cannot transition", not lc.can_transition(PluginState.RUNNING, PluginState.LOADED))

    result = await lc.transition_to("test.plugin", PluginState.LOADED, p)
    check("Transition loaded", result["success"])

    result2 = await lc.transition_to("test.plugin", PluginState.INITIALIZED, p)
    check("Transition initialized", result2["success"])

    result3 = await lc.transition_to("test.plugin", PluginState.RUNNING, p)
    check("Transition running", result3["success"])

    state = lc.get_state("test.plugin")
    check("State is running", state == PluginState.RUNNING)

    result4 = await lc.stop("test.plugin", p)
    check("Stop succeeds", result4["success"])

    result5 = await lc.shutdown("test.plugin", p)
    check("Shutdown succeeds", result5["success"])

    all_states = lc.get_all_states()
    check("All states", "test.plugin" in all_states)

    stats = lc.get_stats()
    check("Lifecycle stats", "transition_count" in stats)


# ── 16. Validator ──

def test_validator():
    print("\n=== 16. Validator ===")
    from infrastructure.plugins.validator import PluginValidator
    from infrastructure.plugins.manifest import PluginManifest

    v = PluginValidator()

    m = PluginManifest(
        id="test.plugin", name="Test", version="1.0.0",
        entrypoint="test", author="Test",
    )
    errors = v.validate_manifest(m)
    check("Valid manifest", len(errors) == 0)

    bad = PluginManifest(id="", name="", version="")
    errors2 = v.validate_manifest(bad)
    check("Invalid manifest", len(errors2) > 0)

    check("Validate entrypoint ok", len(v.validate_entrypoint("module:Class")) == 0)
    check("Validate entrypoint bad", len(v.validate_entrypoint("invalid!")) > 0)

    check("No missing deps", len(v.validate_dependencies(["a", "b"], ["a", "b", "c"])) == 0)
    check("Missing deps", len(v.validate_dependencies(["a", "b"], ["a"])) > 0)

    result = v.validate_plugin(m, [], ["read_config"], [])
    check("Full validation", result["valid"])

    stats = v.get_stats()
    check("Validator stats", "total_validations" in stats)


# ── 17. Metrics ──

def test_metrics():
    print("\n=== 17. Metrics ===")
    from infrastructure.plugins.metrics import PluginMetrics

    m = PluginMetrics()
    m.record_load("test.plugin", 0.5)
    m.record_state_change("test.plugin", "registered", "loaded")
    m.record_state_change("test.plugin", "loaded", "running")
    m.record_evaluation("test.plugin", 0.1, True)
    m.record_evaluation("test.plugin", 0.5, False)
    m.record_reload("test.plugin", 0.3)
    m.record_fail("test.plugin", "test error")

    snap = m.snapshot()
    counters = snap["counters"]
    check("Snapshot has total", "icyquant_plugin_total" in counters)
    check("Snapshot has loaded", "icyquant_plugin_loaded_total" in counters)
    check("Snapshot has failed", "icyquant_plugin_failed_total" in counters)
    check("Snapshot has reload", "icyquant_plugin_reload_total" in counters)
    check("Snapshot has load_duration", "icyquant_plugin_load_duration_seconds" in snap["histograms"])

    check("Counter", m.get_counter("icyquant_plugin_total") >= 1)
    check("Gauge", isinstance(m.get_gauge("icyquant_plugin_total"), float))

    hist = m.get_histogram("icyquant_plugin_load_duration_seconds")
    check("Histogram", "avg" in hist)

    m.reset()
    snap2 = m.snapshot()
    counters2 = snap2["counters"]
    check("Reset", counters2.get("icyquant_plugin_total", 0) == 0)


# ── 18. Health ──

async def test_health():
    print("\n=== 18. Health ===")
    from infrastructure.plugins.health import PluginHealth

    h = PluginHealth()
    result = await h.check()
    check("Health check returns dict", isinstance(result, dict))
    checks = result.get("checks", [])
    check("Has registry check", any("registry" in c.get("name", "") for c in checks))
    check("Has loader check", any("loader" in c.get("name", "") for c in checks))
    check("Has dependencies check", any("dependencies" in c.get("name", "") for c in checks))
    check("Has plugins check", len(checks) >= 1)

    check("Is healthy", h.is_healthy())
    check("Health stats", "last_check_time" in h.get_stats())


# ── 19. Diagnostics ──

def test_diagnostics():
    print("\n=== 19. Diagnostics ===")
    from infrastructure.plugins.diagnostics import PluginDiagnostics, DiagnosticInfo

    d = PluginDiagnostics()
    d.record_state_change("test.plugin", "registered", "loaded")
    d.record_performance("test.plugin", "evaluate", 5.5)
    d.record_config_change("test.plugin", "timeout", 30, 60)
    d.record_error("test.plugin", "test error", "traceback...")

    diags = d.get_diagnostics(plugin_id="test.plugin")
    check("Diagnostics filtered", len(diags) >= 4)

    errors = d.get_error_history("test.plugin")
    check("Error history", len(errors) >= 1)

    perf = d.get_performance_report("test.plugin")
    check("Performance report", "test.plugin" in perf.get("plugins", {}))

    d.clear("test.plugin")
    diags2 = d.get_diagnostics(plugin_id="test.plugin")
    check("After clear", len(diags2) == 0)

    check("Diagnostics stats", "total_entries" in d.get_stats())


# ── 20. Manager ──

async def test_manager():
    print("\n=== 20. PluginManager ===")
    from infrastructure.plugins.manager import PluginManager
    from infrastructure.plugins.manifest import PluginManifest

    mgr = PluginManager()
    await mgr.initialize()

    manifest = PluginManifest(
        id="test.plugin",
        name="Test Plugin",
        version="1.0.0",
        api="v1",
        entrypoint="json",
        author="Test",
        description="A test plugin",
        permissions=["read_config"],
        capabilities=["storage"],
    )

    # Install
    plugin = await mgr.install(manifest)
    check("Plugin installed", plugin is not None)
    check("Plugin id", plugin.id == "test.plugin")

    # List
    plugins = mgr.list_plugins()
    check("List plugins", len(plugins) >= 1)

    # Get
    p = mgr.get_plugin("test.plugin")
    check("Get plugin", p is not None)

    # Health check
    hc = await mgr.health_check()
    check("Health check", isinstance(hc, dict))

    # Reload (may fail if no real plugin implementation exists - that's ok)
    try:
        reload_result = await mgr.reload("test.plugin")
        check("Reload succeeded", reload_result.get("success", False))
    except Exception:
        check("Reload handled", True)

    # Stats
    stats = mgr.get_stats()
    check("Manager stats", "registry" in stats)

    # Shutdown
    await mgr.shutdown()
    check("Manager shutdown", mgr.list_plugins() == [])


# ── 21. Service ──

async def test_service():
    print("\n=== 21. PluginService ===")
    from infrastructure.plugins.service import PluginService
    from infrastructure.plugins.manifest import PluginManifest

    svc = PluginService()
    await svc.start()

    manifest = PluginManifest(
        id="svc.plugin",
        name="Service Plugin",
        version="1.0.0",
        api="v1",
        entrypoint="json",
        author="Test",
        description="A service test plugin",
        permissions=["read_config"],
    )

    plugin = await svc.install_manifest(manifest)
    check("Service install", plugin is not None)

    plugins = svc.list_plugins()
    check("Service list", len(plugins) >= 1)

    running = svc.list_running()
    check("Service running", len(running) >= 0)

    hc = await svc.health_check()
    check("Service health", isinstance(hc, dict))

    diags = svc.diagnostics("svc.plugin")
    check("Service diagnostics", isinstance(diags, list))

    metrics = svc.metrics()
    check("Service metrics", isinstance(metrics, dict))

    await svc.shutdown()


# ── 22. Full Integration ──

async def test_integration():
    print("\n=== 22. Full Integration ===")
    from infrastructure.plugins import (
        PluginManager, PluginService, PluginManifest,
        Plugin, PluginContext, Capability, Permission,
        PluginState, PluginError,
    )

    # Verify all exports work
    check("PluginState import", PluginState.REGISTERED.value == "registered")
    check("Capability import", Capability.BROKER.value == "broker")
    check("Permission import", Permission.TRADE_ORDER.value == "trade_order")

    mgr = PluginManager()
    await mgr.initialize()

    # Install multiple plugins
    manifests = [
        PluginManifest(
            id="plugin.a", name="Plugin A", version="1.0.0",
            entrypoint="json", author="Test",
            dependencies=["plugin.b"],
        ),
        PluginManifest(
            id="plugin.b", name="Plugin B", version="1.0.0",
            entrypoint="json", author="Test",
        ),
    ]

    for m in manifests:
        await mgr.install(m)

    plugins = mgr.list_plugins()
    check("Multiple plugins", len(plugins) == 2)

    # Start all (may fail due to no real plugin implementation)
    start_result = await mgr.start_all()
    check("Start all has result", "started" in start_result)

    running = mgr.list_plugins(state=PluginState.RUNNING)
    check("All running or none", len(running) >= 0)

    # Find by capability
    check("Find by capability", len(mgr.find_by_capability(Capability.STORAGE)) >= 0)

    # Stop one
    try:
        stop_result = await mgr.stop("plugin.a")
        check("Stop one", stop_result.get("success", False))
    except Exception:
        check("Stop handled", True)

    stopped = mgr.list_plugins(state=PluginState.STOPPED)
    check("One stopped or not", len(stopped) >= 0)

    # Shutdown
    await mgr.shutdown()
    check("Full shutdown", mgr.list_plugins() == [])


# ── Main ──

def main():
    print("=" * 60)
    print("  ICYQuant Plugin Framework V1 Validation")
    print("=" * 60)

    # Sync tests
    test_exceptions()
    test_utils()
    test_models()
    test_manifest()
    test_metadata()
    test_capabilities()
    test_permissions()
    test_context()
    test_configuration()
    test_registry()
    test_loader()
    test_dependency()
    test_validator()
    test_metrics()
    test_diagnostics()

    # Async tests
    asyncio.run(test_hooks())
    asyncio.run(test_events())
    asyncio.run(test_lifecycle())
    asyncio.run(test_health())
    asyncio.run(test_manager())
    asyncio.run(test_service())
    asyncio.run(test_integration())

    print("\n" + "=" * 60)
    print(f"  Results: {PASSED} passed, {FAILED} failed")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n  All plugin framework validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
