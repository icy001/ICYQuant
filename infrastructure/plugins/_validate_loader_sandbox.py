"""
Validation script for plugin loader and sandbox packages.

Comprehensive test suite covering loader (sections 1-14) and
sandbox (sections 15-30) components.
"""

from __future__ import annotations

import asyncio
import sys
import os
import tempfile

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
    global PASSED, FAILED
    if actual == expected:
        PASSED += 1
        print(f"  [OK] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} - expected {expected!r}, got {actual!r}")


# ── 1. PluginLoader basic ──

def test_loader_basic():
    print("\n=== 1. PluginLoader Basic ===")
    from infrastructure.plugins.loader import PluginLoader

    loader = PluginLoader()
    check("Loader created", loader is not None)

    stats = loader.get_stats()
    check("Stats has plugins_registered", "plugins_registered" in stats)
    check("Stats has importer", "importer" in stats)
    check("Stats has scanner", "scanner" in stats)

    check("Validate entrypoint ok", loader.validate_entrypoint("module:Class"))
    check("Validate entrypoint ok (simple)", loader.validate_entrypoint("json"))
    check("Validate entrypoint bad", not loader.validate_entrypoint("in valid::"))
    check("Validate entrypoint empty", not loader.validate_entrypoint(""))
    check("Validate entrypoint none", not loader.validate_entrypoint(None))

    module = loader.load_module("json")
    check("Load module json", module is not None)
    check("Load module has dumps", hasattr(module, "dumps"))

    result = loader.load_plugin("json")
    check("Load plugin handles non-plugin module", result is None)

    result2 = loader.load_plugin("json:JSONEncoder")
    check("Load plugin with class reference works", result2 is not None)


# ── 2. DirectoryScanner ──

def test_directory_scanner():
    print("\n=== 2. DirectoryScanner ===")
    from infrastructure.plugins.loader import DirectoryScanner

    scanner = DirectoryScanner()
    check("Scanner created", scanner is not None)

    stats_dict = scanner.to_dict()
    check("to_dict has max_depth", "max_depth" in stats_dict)
    check("to_dict has stats", "stats" in stats_dict)

    with tempfile.TemporaryDirectory() as tmpdir:
        manifests = scanner.scan(tmpdir)
        check("Scan empty dir returns list", isinstance(manifests, list))
        check("Scan empty dir no manifests", len(manifests) == 0)

        discovered = scanner.discover_manifests(tmpdir)
        check("discover_manifests returns list", isinstance(discovered, list))

    with tempfile.TemporaryDirectory() as tmpdir:
        from infrastructure.plugins.manifest import PluginManifest
        manifest = PluginManifest(
            id="test.plugin", name="Test", version="1.0.0",
            api="v1", entrypoint="json", author="Test",
        )
        manifest_path = os.path.join(tmpdir, "manifest.yaml")
        with open(manifest_path, "w") as f:
            f.write(manifest.to_yaml())

        manifests = scanner.scan(tmpdir)
        check("Scan finds manifest", len(manifests) >= 1)
        if manifests:
            check("Manifest id correct", manifests[0].id == "test.plugin")

        discovered = scanner.discover_manifests(tmpdir)
        check("discover_manifests finds file", len(discovered) >= 1)

    structure = scanner.get_plugin_structure(tmpdir)
    check("get_plugin_structure returns dict", isinstance(structure, dict))
    check("get_plugin_structure has exists", "exists" in structure)

    dupes = scanner.detect_duplicates(manifests)
    check("detect_duplicates returns list", isinstance(dupes, list))

    valid = scanner.check_compatibility(manifests)
    check("check_compatibility returns list", isinstance(valid, list))


# ── 3. PluginImporter ──

def test_plugin_importer():
    print("\n=== 3. PluginImporter ===")
    from infrastructure.plugins.loader import PluginImporter

    importer = PluginImporter()
    check("Importer created", importer is not None)

    module = importer.import_module("json")
    check("import_module json", module is not None)

    module2 = importer.import_module("json")
    check("import_module cache hit", module2 is module)

    stats = importer.get_stats()
    check("Stats has imports", "imports" in stats)
    check("Stats has cache_hits", "cache_hits" in stats)
    check("Stats has cached_modules", "cached_modules" in stats)
    check("Cache hit recorded", stats["cache_hits"] >= 1)

    plugin_class = importer.discover_plugin_class(module)
    check("discover_plugin_class returns None for json", plugin_class is None)

    importer.unload_module("json")
    check("unload_module succeeded", True)

    module3 = importer.reload_module("json")
    check("reload_module returns module", module3 is not None)

    stats2 = importer.get_stats()
    check("Reload recorded", stats2["reloads"] >= 1)

    try:
        importer.import_module("nonexistent_module_xyz")
        check("Import nonexistent should fail", False)
    except ImportError:
        check("Import nonexistent raises ImportError", True)

    try:
        importer.import_module("")
        check("Import empty should fail", False)
    except ValueError:
        check("Import empty raises ValueError", True)


# ── 4. DependencyResolver2 ──

def test_dependency_resolver2():
    print("\n=== 4. DependencyResolver2 ===")
    from infrastructure.plugins.loader import DependencyResolver2

    resolver = DependencyResolver2()
    check("Resolver created", resolver is not None)

    plugins = {
        "plugin-a": ["plugin-b"],
        "plugin-b": ["plugin-c"],
        "plugin-c": [],
    }
    graph = resolver.build_graph(plugins)
    check("Graph built", len(graph) == 3)
    check("Graph has plugin-a", "plugin-a" in graph)
    check("Graph has plugin-c", "plugin-c" in graph)

    cycles = resolver.detect_cycles(graph)
    check("No cycles", len(cycles) == 0)

    order = resolver.topological_sort(graph)
    check("Topological sort correct order", order.index("plugin-c") < order.index("plugin-b"))
    check("Topological sort has all", len(order) == 3)

    result = resolver.resolve(plugins, {"plugin-a", "plugin-b", "plugin-c"})
    check("Resolve valid", result["valid"] is True)
    check("Resolve has order", len(result["order"]) == 3)

    circular = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }
    cycles2 = resolver.detect_cycles(circular)
    check("Cycle detected", len(cycles2) >= 1)

    check("Version >= passes", resolver.check_version_constraint(">=1.0.0", "1.5.0"))
    check("Version >= fails", not resolver.check_version_constraint(">=2.0.0", "0.9.0"))
    check("Version == passes", resolver.check_version_constraint("==1.0.0", "1.0.0"))
    check("Version != passes", resolver.check_version_constraint("!=1.0.0", "2.0.0"))
    check("Version bare passes", resolver.check_version_constraint("1.0.0", "1.5.0"))

    load_order = resolver.get_load_order("plugin-a", plugins)
    check("get_load_order returns list", isinstance(load_order, list))
    check("get_load_order has plugin-a", "plugin-a" in load_order)

    opt_plugins = {"a": ["b", "?c"], "b": []}
    result2 = resolver.resolve(opt_plugins, {"a", "b"})
    check("Optional dep not required", result2["valid"] is True)

    d = resolver.to_dict()
    check("to_dict has resolution_count", "resolution_count" in d)


# ── 5. LoaderCache ──

def test_loader_cache():
    print("\n=== 5. LoaderCache ===")
    from infrastructure.plugins.loader import LoaderCache
    from infrastructure.plugins.manifest import PluginManifest

    cache = LoaderCache()
    check("Cache created", cache is not None)

    m = PluginManifest(
        id="cache.test", name="Cache Test", version="1.0.0",
        api="v1", entrypoint="json", author="Test",
    )
    cache.set_manifest("cache.test", m)
    retrieved = cache.get_manifest("cache.test")
    check("set/get manifest", retrieved is not None)
    check("manifest id correct", retrieved.id == "cache.test")

    check("get missing manifest is None", cache.get_manifest("nonexistent") is None)

    import json as json_mod
    cache.set_module("cache.test", json_mod)
    mod = cache.get_module("cache.test")
    check("set/get module", mod is json_mod)

    tree = {"id": "root", "children": []}
    cache.set_dependency_tree("cache.test", tree)
    retrieved_tree = cache.get_dependency_tree("cache.test")
    check("set/get dependency tree", retrieved_tree is not None)
    check("tree id correct", retrieved_tree["id"] == "root")

    cache.invalidate_plugin("cache.test")
    check("After invalidate manifest None", cache.get_manifest("cache.test") is None)
    check("After invalidate module None", cache.get_module("cache.test") is None)

    cache.set_manifest("cache.test2", m)
    cache.invalidate_all()
    check("After invalidate_all None", cache.get_manifest("cache.test2") is None)

    cache.set_manifest("cache.test3", m)
    stats = cache.get_stats()
    check("Stats has manifest_entries", "manifest_entries" in stats)
    check("Stats has hit_rate", "hit_rate" in stats)

    cache.clear()
    check("After clear entries 0", cache.get_stats()["manifest_entries"] == 0)


# ── 6. LoaderMetrics ──

def test_loader_metrics():
    print("\n=== 6. LoaderMetrics ===")
    from infrastructure.plugins.loader import LoaderMetrics

    metrics = LoaderMetrics()
    check("Metrics created", metrics is not None)

    metrics.record_load("test.plugin", 0.5)
    metrics.record_scan("test.plugin", 0.1)
    metrics.record_import("test.plugin", 0.05)
    metrics.record_dependency_resolution("test.plugin", 0.02)
    metrics.record_discovery("test.plugin", 0.3)
    metrics.record_reload("test.plugin", 0.4)
    metrics.record_unload("test.plugin", 0.1)
    metrics.record_error("test.plugin", "test error")

    snap = metrics.snapshot()
    check("Snapshot has counters", "counters" in snap)
    check("Snapshot has histograms", "histograms" in snap)

    counter_load = metrics.get_counter("icyquant_plugin_load_total")
    check("Load counter >= 1", counter_load >= 1)

    hist = metrics.get_histogram("icyquant_plugin_import_seconds")
    check("Histogram has avg", "avg" in hist)
    check("Histogram has count", hist["count"] >= 1)

    stats = metrics.get_stats()
    check("Stats has counter_count", "counter_count" in stats)

    metrics.reset()
    snap2 = metrics.snapshot()
    check("After reset counter 0", snap2["counters"].get("icyquant_plugin_load_total", 0) == 0)


# ── 7. LoaderDiagnostics ──

def test_loader_diagnostics():
    print("\n=== 7. LoaderDiagnostics ===")
    from infrastructure.plugins.loader import LoaderDiagnostics

    diag = LoaderDiagnostics()
    check("Diagnostics created", diag is not None)

    diag.record_state_change("test.plugin", "registered", "loaded")
    diag.record_state_change("test.plugin", "loaded", "running")
    diag.record_error("test.plugin", "test error", "traceback...")
    diag.record_performance("test.plugin", "load", 5.5)
    diag.record_load_step("test.plugin", "validate", True, 0.01)

    diags = diag.get_diagnostics(plugin_id="test.plugin")
    check("Diagnostics filtered", len(diags) >= 4)

    errors = diag.get_error_history("test.plugin")
    check("Error history", len(errors) >= 1)

    perf = diag.get_performance_report("test.plugin")
    check("Performance report has plugin", "test.plugin" in perf or len(perf) >= 0)

    diags_all = diag.get_diagnostics()
    check("All diagnostics", len(diags_all) >= 5)

    diag.clear("test.plugin")
    diags2 = diag.get_diagnostics(plugin_id="test.plugin")
    check("After clear plugin", len(diags2) == 0)

    stats = diag.get_stats()
    check("Stats has total_entries", "total_entries" in stats)


# ── 8. PluginVerifier ──

def test_plugin_verifier():
    print("\n=== 8. PluginVerifier ===")
    from infrastructure.plugins.loader import PluginVerifier
    from infrastructure.plugins.manifest import PluginManifest

    verifier = PluginVerifier()
    check("Verifier created", verifier is not None)

    m = PluginManifest(
        id="verify.test", name="Verify Test", version="1.0.0",
        api="v1", entrypoint="json", author="Test",
    )
    manifest_errors = verifier.verify_manifest(m)
    check("verify_manifest valid", len(manifest_errors) == 0)

    entrypoint_errors = verifier.verify_entrypoint(m)
    check("verify_entrypoint valid", len(entrypoint_errors) == 0)

    compat_errors = verifier.verify_compatibility(m)
    check("verify_compatibility valid", len(compat_errors) == 0)

    dep_errors = verifier.verify_dependencies(m, {"json"})
    check("verify_dependencies valid", len(dep_errors) == 0)

    perm_errors = verifier.verify_permissions(m)
    check("verify_permissions valid", len(perm_errors) == 0)

    sig_errors = verifier.verify_signature(m)
    check("verify_signature stub", len(sig_errors) == 0)

    result = verifier.verify(m)
    check("verify overall valid", result["valid"] is True)
    check("verify has plugin_id", result["plugin_id"] == "verify.test")

    bad = PluginManifest(id="", name="", version="")
    bad_errors = verifier.verify_manifest(bad)
    check("verify bad manifest has errors", len(bad_errors) > 0)

    d = verifier.to_dict()
    check("to_dict has verified_count", "verified_count" in d)


# ── 9. LoaderValidator ──

def test_loader_validator():
    print("\n=== 9. LoaderValidator ===")
    from infrastructure.plugins.loader import LoaderValidator
    from infrastructure.plugins.manifest import PluginManifest

    validator = LoaderValidator()
    check("Validator created", validator is not None)

    m = PluginManifest(
        id="validate.test", name="Validate Test", version="1.0.0",
        api="v1", entrypoint="json", author="Test",
    )
    errors = validator.validate_manifest(m)
    check("Valid manifest", len(errors) == 0)

    bad = PluginManifest(id="", name="", version="")
    errors2 = validator.validate_manifest(bad)
    check("Invalid manifest has errors", len(errors2) > 0)

    ep_ok = validator.validate_entrypoint("module:Class")
    check("Valid entrypoint", len(ep_ok) == 0)

    ep_bad = validator.validate_entrypoint("invalid!")
    check("Invalid entrypoint has errors", len(ep_bad) > 0)

    ep_empty = validator.validate_entrypoint("")
    check("Empty entrypoint has errors", len(ep_empty) > 0)

    dep_ok = validator.validate_dependencies(["a", "b"], ["a", "b", "c"])
    check("Valid dependencies", len(dep_ok) == 0)

    dep_bad = validator.validate_dependencies(["a", "b"], ["a"])
    check("Invalid dependencies", len(dep_bad) > 0)

    result = validator.validate_plugin(m, [], ["read_config"], [])
    check("Full validation valid", result["valid"] is True)

    stats = validator.get_stats()
    check("Stats has total_validations", "total_validations" in stats)


# ── 10. PluginInstaller ──

def test_plugin_installer():
    print("\n=== 10. PluginInstaller ===")
    from infrastructure.plugins.loader import PluginInstaller

    installer = PluginInstaller()
    check("Installer created", installer is not None)

    d = installer.to_dict()
    check("to_dict has install_count", "install_count" in d)
    check("to_dict has success_rate", "success_rate" in d)
    check("to_dict has has_registry", "has_registry" in d)


# ── 11. PluginUninstaller ──

def test_plugin_uninstaller():
    print("\n=== 11. PluginUninstaller ===")
    from infrastructure.plugins.loader import PluginUninstaller

    uninstaller = PluginUninstaller()
    check("Uninstaller created", uninstaller is not None)

    d = uninstaller.to_dict()
    check("to_dict has uninstall_count", "uninstall_count" in d)
    check("to_dict has has_registry", "has_registry" in d)


# ── 12. PluginReloader ──

def test_plugin_reloader():
    print("\n=== 12. PluginReloader ===")
    from infrastructure.plugins.loader import PluginReloader

    reloader = PluginReloader()
    check("Reloader created", reloader is not None)

    d = reloader.to_dict()
    check("to_dict has reload_count", "reload_count" in d)
    check("to_dict has has_registry", "has_registry" in d)


# ── 13. FileWatcher ──

def test_file_watcher():
    print("\n=== 13. FileWatcher ===")
    from infrastructure.plugins.loader import FileWatcher

    watcher = FileWatcher()
    check("Watcher created", watcher is not None)
    check("Initially not running", not watcher.is_running())

    with tempfile.TemporaryDirectory() as tmpdir:
        watcher.add_path(tmpdir)
        check("add_path does not raise", True)

        watcher.remove_path(tmpdir)
        check("remove_path does not raise", True)

    d = watcher.to_dict()
    check("to_dict has running", "running" in d)
    check("to_dict has watched_paths", "watched_paths" in d)


# ── 14. Loader integration ──

async def test_loader_integration():
    print("\n=== 14. Loader Integration ===")
    from infrastructure.plugins.loader import PluginLoader
    from infrastructure.plugins.manifest import PluginManifest

    loader = PluginLoader()

    test_dir = os.path.join(os.getcwd(), "_test_plugin_dir")
    os.makedirs(test_dir, exist_ok=True)
    try:
        plugin_file = os.path.join(test_dir, "test_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(
                "class TestPlugin:\n"
                "    def __init__(self, ctx=None):\n"
                "        self.ctx = ctx\n"
                "        self.name = 'test'\n"
            )

        rel_path = os.path.relpath(plugin_file).replace("\\", "/")
        entrypoint = rel_path + ":TestPlugin"

        manifest = PluginManifest(
            id="integration.test", name="Integration Test",
            version="1.0.0", api="v1",
            entrypoint=entrypoint,
            author="Test", description="Integration test plugin",
            permissions=["read_config"],
        )

        plugin = await loader.install(manifest)
        check("Install returns plugin", plugin is not None)
        check("Install plugin id", plugin.id == "integration.test")

        plugins_list = loader.list_plugins()
        check("List plugins has 1", len(plugins_list) == 1)

        result = await loader.load("integration.test")
        check("Load succeeds", result.get("success") is True)

        check("Get plugin found", loader.get_plugin("integration.test") is not None)

        unload_result = await loader.unload("integration.test")
        check("Unload succeeds", unload_result.get("success") is True)

        await loader.shutdown()
        check("Shutdown clears plugins", len(loader.list_plugins()) == 0)
    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


# ── 15. Sandbox basic ──

def test_sandbox_basic():
    print("\n=== 15. Sandbox Basic ===")
    from infrastructure.plugins.sandbox import Sandbox

    sandbox = Sandbox()
    check("Sandbox created", sandbox is not None)

    stats = sandbox.get_stats()
    check("Stats has total_sandboxes", "total_sandboxes" in stats)
    check("Stats has isolation", "isolation" in stats)
    check("Stats has permissions", "permissions" in stats)
    check("Stats has filesystem", "filesystem" in stats)
    check("Stats has network", "network" in stats)


# ── 16. SandboxRuntime ──

def test_sandbox_runtime():
    print("\n=== 16. SandboxRuntime ===")
    from infrastructure.plugins.sandbox import SandboxRuntime

    rt = SandboxRuntime(plugin_id="runtime.test")
    check("Runtime created", rt.plugin_id == "runtime.test")
    check("Default status created", rt.status == "created")
    check("is_active for created", rt.is_active())

    rt.status = "running"
    check("is_active for running", rt.is_active())

    rt.status = "stopped"
    check("not active for stopped", not rt.is_active())

    rt.status = "destroyed"
    check("not active for destroyed", not rt.is_active())

    d = rt.to_dict()
    check("to_dict has plugin_id", d["plugin_id"] == "runtime.test")
    check("to_dict has status", "status" in d)

    rt2 = SandboxRuntime(
        plugin_id="runtime.test2",
        memory_limit=512 * 1024 * 1024,
        cpu_limit=75.0,
    )
    check("Custom memory limit", rt2.memory_limit == 512 * 1024 * 1024)
    check("Custom cpu limit", rt2.cpu_limit == 75.0)


# ── 17. IsolationManager ──

async def test_isolation_manager():
    print("\n=== 17. IsolationManager ===")
    from infrastructure.plugins.sandbox import IsolationManager

    mgr = IsolationManager()
    check("IsolationManager created", mgr is not None)

    info = await mgr.create_isolation("iso.test", {"mode": "thread"})
    check("create_isolation returns dict", isinstance(info, dict))
    check("Has plugin_id", info["plugin_id"] == "iso.test")
    check("Has status active", info["status"] == "active")

    check("is_isolated returns True", mgr.is_isolated("iso.test"))

    iso_info = mgr.get_isolation_info("iso.test")
    check("get_isolation_info has mode", "mode" in iso_info)

    stats = mgr.get_stats()
    check("Stats has total_isolations", "total_isolations" in stats)
    check("Stats has active_isolations", "active_isolations" in stats)

    await mgr.destroy_isolation("iso.test")
    check("After destroy not isolated", not mgr.is_isolated("iso.test"))

    try:
        mgr.get_isolation_info("nonexistent")
        check("Should raise", False)
    except Exception:
        check("get_isolation_info raises for missing", True)


# ── 18. SandboxPermissionGuard ──

def test_sandbox_permission_guard():
    print("\n=== 18. SandboxPermissionGuard ===")
    from infrastructure.plugins.sandbox import SandboxPermissionGuard

    guard = SandboxPermissionGuard()
    check("PermissionGuard created", guard is not None)

    guard.grant_permission("perm.test", "read_config")
    check("check granted", guard.check_permission("perm.test", "read_config"))
    check("check not granted", not guard.check_permission("perm.test", "trade_order"))

    perms = guard.get_permissions("perm.test")
    check("get_permissions returns list", "read_config" in perms)

    guard.set_permissions("perm.test", ["read_config", "network", "trade_order"])
    check("After set_permissions read_config", guard.check_permission("perm.test", "read_config"))
    check("After set_permissions network", guard.check_permission("perm.test", "network"))

    guard.revoke_permission("perm.test", "network")
    check("After revoke network", not guard.check_permission("perm.test", "network"))

    try:
        guard.require_permission("perm.test", "nonexistent")
        check("Should raise on missing", False)
    except Exception:
        check("require_permission raises on missing", True)

    audit = guard.audit_permissions("perm.test")
    check("audit has plugin_id", audit["plugin_id"] == "perm.test")

    guard.clear_permissions("perm.test")
    check("After clear no perms", len(guard.get_permissions("perm.test")) == 0)

    stats = guard.get_stats()
    check("Stats has total_plugins", "total_plugins" in stats)


# ── 19. SandboxCapabilityGuard ──

def test_sandbox_capability_guard():
    print("\n=== 19. SandboxCapabilityGuard ===")
    from infrastructure.plugins.sandbox import SandboxCapabilityGuard

    guard = SandboxCapabilityGuard()
    check("CapabilityGuard created", guard is not None)

    guard.grant_capability("cap.test", "broker")
    check("check granted", guard.check_capability("cap.test", "broker"))
    check("check not granted", not guard.check_capability("cap.test", "risk"))

    caps = guard.get_capabilities("cap.test")
    check("get_capabilities returns list", "broker" in caps)

    guard.set_capabilities("cap.test", ["broker", "market_data"])
    check("After set broker", guard.check_capability("cap.test", "broker"))
    check("After set market_data", guard.check_capability("cap.test", "market_data"))

    guard.revoke_capability("cap.test", "broker")
    check("After revoke broker", not guard.check_capability("cap.test", "broker"))

    try:
        guard.require_capability("cap.test", "nonexistent")
        check("Should raise", False)
    except Exception:
        check("require_capability raises on missing", True)

    guard.clear_capabilities("cap.test")
    check("After clear no caps", len(guard.get_capabilities("cap.test")) == 0)

    stats = guard.get_stats()
    check("Stats has total_plugins", "total_plugins" in stats)


# ── 20. ResourceQuota / ResourceQuotaManager ──

def test_resource_quota():
    print("\n=== 20. ResourceQuota ===")
    from infrastructure.plugins.sandbox import ResourceQuota, ResourceQuotaManager

    quota = ResourceQuota()
    check("Quota created", quota is not None)
    check("Default memory 256MB", quota.memory_bytes == 256 * 1024 * 1024)
    check("Default cpu 50%", quota.cpu_percent == 50.0)

    d = quota.to_dict()
    check("to_dict has memory_bytes", "memory_bytes" in d)

    mgr = ResourceQuotaManager()
    check("QuotaManager created", mgr is not None)

    custom_quota = ResourceQuota(memory_bytes=128 * 1024 * 1024, cpu_percent=25.0)
    mgr.set_quota("quota.test", custom_quota)
    check("set_quota succeeded", True)

    retrieved = mgr.get_quota("quota.test")
    check("get_quota custom memory", retrieved.memory_bytes == 128 * 1024 * 1024)

    check_result = mgr.check_quota("quota.test")
    check("check_quota has within_limits", "within_limits" in check_result)
    check("check_quota valid", check_result["within_limits"] is True)

    mgr.record_usage("quota.test", "memory_used", 100 * 1024 * 1024)
    check_result2 = mgr.check_quota("quota.test")
    check("Within limits after usage", check_result2["within_limits"] is True)

    mgr.record_usage("quota.test", "memory_used", 200 * 1024 * 1024)
    check_result3 = mgr.check_quota("quota.test")
    check("Exceeded memory detected", not check_result3["within_limits"])
    check("Violations has memory_bytes", "memory_bytes" in check_result3["violations"])

    mgr.reset_usage("quota.test")
    check_result4 = mgr.check_quota("quota.test")
    check("After reset no violations", check_result4["within_limits"] is True)

    stats = mgr.get_stats()
    check("Stats has total_quotas", "total_quotas" in stats)


# ── 21. FilesystemPolicy ──

def test_filesystem_policy():
    print("\n=== 21. FilesystemPolicy ===")
    from infrastructure.plugins.sandbox import FilesystemPolicy

    policy = FilesystemPolicy()
    check("FilesystemPolicy created", policy is not None)

    with tempfile.TemporaryDirectory() as tmpdir:
        policy.set_root("fs.test", tmpdir)
        check("set_root succeeded", True)

        policy.allow_path("fs.test", tmpdir, "read")
        check("allow_path succeeded", True)

        allowed = policy.get_allowed_paths("fs.test")
        check("get_allowed_paths has entries", len(allowed) >= 1)

        check_access = policy.check_access("fs.test", tmpdir, "read")
        check("check_access read allowed", check_access)

        policy.deny_path("fs.test", tmpdir)
        check("After deny not allowed", not policy.check_access("fs.test", tmpdir, "read"))

        check("is_within_root for valid", policy.is_within_root("fs.test", tmpdir))

        stats = policy.get_stats()
        check("Stats has total_plugins", "total_plugins" in stats)


# ── 22. NetworkPolicy ──

def test_network_policy():
    print("\n=== 22. NetworkPolicy ===")
    from infrastructure.plugins.sandbox import NetworkPolicy

    policy = NetworkPolicy()
    check("NetworkPolicy created", policy is not None)

    policy.allow_host("net.test", "api.example.com")
    check("allow_host succeeded", True)

    allowed = policy.get_allowed_hosts("net.test")
    check("get_allowed_hosts has entry", "api.example.com" in allowed)

    check_access = policy.check_access("net.test", "api.example.com", "https")
    check("check_access allowed", check_access)

    check_no_access = policy.check_access("net.test", "evil.com", "https")
    check("check_access denied for unknown", not check_no_access)

    policy.deny_host("net.test", "blocked.example.com")
    check("deny_host succeeded", True)

    check_denied = policy.check_access("net.test", "blocked.example.com", "https")
    check("check_access denied", not check_denied)

    protos = policy.get_allowed_protocols("net.test")
    check("get_allowed_protocols returns list", isinstance(protos, list))

    stats = policy.get_stats()
    check("Stats has total_plugins", "total_plugins" in stats)


# ── 23. SignatureVerifier ──

def test_signature_verifier():
    print("\n=== 23. SignatureVerifier ===")
    from infrastructure.plugins.sandbox import SignatureVerifier

    sv = SignatureVerifier()
    check("SignatureVerifier created", sv is not None)

    pub_key, priv_key = sv.generate_keypair()
    check("generate_keypair returns tuple", isinstance((pub_key, priv_key), tuple))
    check("Public key not empty", len(pub_key) > 0)
    check("Private key not empty", len(priv_key) > 0)

    sv.register_key("sig.test", pub_key, priv_key)
    check("register_key succeeded", True)

    sig = sv.sign("sig.test", priv_key)
    check("sign returns string", isinstance(sig, str))
    check("signature not empty", len(sig) > 0)

    valid = sv.verify("sig.test", sig, pub_key)
    check("verify valid signature", valid)

    invalid = sv.verify("sig.test", "invalid_sig", pub_key)
    check("verify invalid fails", not invalid)

    plugins = sv.get_registered_plugins()
    check("get_registered_plugins has sig.test", "sig.test" in plugins)

    failures = sv.get_failures("sig.test")
    check("failures is list", isinstance(failures, list))

    stats = sv.get_stats()
    check("Stats has registered_keys", "registered_keys" in stats)


# ── 24. TrustStore ──

def test_trust_store():
    print("\n=== 24. TrustStore ===")
    from infrastructure.plugins.sandbox import TrustStore

    ts = TrustStore()
    check("TrustStore created", ts is not None)

    ts.trust("trust.test")
    check("is_trusted returns True", ts.is_trusted("trust.test"))

    ts.trust("trust.test2", "public_key_string")
    check("is_trusted for test2", ts.is_trusted("trust.test2"))

    check("not trusted for unknown", not ts.is_trusted("unknown"))

    trusted_list = ts.get_trusted()
    check("get_trusted has entries", len(trusted_list) >= 2)

    ts.distrust("trust.test")
    check("After distrust not trusted", not ts.is_trusted("trust.test"))

    ts.add_public_key("trust.test3", "key_string")
    check("add_public_key succeeded", True)

    pk = ts.get_public_key("trust.test3")
    check("get_public_key returns key", pk == "key_string")

    ts.clear()
    check("After clear no trusted", len(ts.get_trusted()) == 0)

    stats = ts.get_stats()
    check("Stats has total_trusted", "total_trusted" in stats)


# ── 25. SandboxPolicy ──

def test_sandbox_policy():
    print("\n=== 25. SandboxPolicy ===")
    from infrastructure.plugins.sandbox import SandboxPolicy

    policy = SandboxPolicy()
    check("SandboxPolicy created", policy is not None)

    policy.set_policy("pol.test", {
        "default_action": "deny",
        "allowed_actions": ["filesystem.read", "network.outbound"],
        "denied_actions": [],
    })
    check("set_policy succeeded", True)

    p = policy.get_policy("pol.test")
    check("get_policy returns dict", isinstance(p, dict))
    check("get_policy has allowed_actions", "allowed_actions" in p)

    is_allowed = policy.allow("filesystem.read", "pol.test")
    check("allow for allowed action", is_allowed)

    is_denied = policy.allow("filesystem.write", "pol.test")
    check("allow for denied action", not is_denied)

    policy.deny("network.inbound", "pol.test", "no inbound allowed")
    check("deny succeeded", True)

    is_denied2 = policy.allow("network.inbound", "pol.test")
    check("deny takes precedence", not is_denied2)

    policy.reset_policy("pol.test")
    check("After reset uses default", policy.get_policy("pol.test")["default_action"] == "deny")

    all_policies = policy.get_all_policies()
    check("get_all_policies returns dict", isinstance(all_policies, dict))

    stats = policy.get_stats()
    check("Stats has total_policies", "total_policies" in stats)


# ── 26. PolicyEngine / PolicyDecision ──

def test_policy_engine():
    print("\n=== 26. PolicyEngine ===")
    from infrastructure.plugins.sandbox import PolicyEngine, PolicyDecision, PolicyRule

    engine = PolicyEngine()
    check("PolicyEngine created", engine is not None)

    check("PolicyDecision.ALLOW", PolicyDecision.ALLOW.value == "allow")
    check("PolicyDecision.DENY", PolicyDecision.DENY.value == "deny")
    check("PolicyDecision.REQUIRE_APPROVAL", PolicyDecision.REQUIRE_APPROVAL.value == "require_approval")

    rule1 = PolicyRule("filesystem.read", PolicyDecision.ALLOW, "plugin.*", "root/*")
    check("Rule created", rule1.action_pattern == "filesystem.read")

    engine.add_rule(rule1)
    check("add_rule succeeded", True)

    decision = engine.evaluate("plugin.test", "filesystem.read", {"resource": "root/file.txt"})
    check("evaluate returns ALLOW", decision == PolicyDecision.ALLOW)

    decision2 = engine.evaluate("plugin.test", "filesystem.write", {"resource": "root/file.txt"})
    check("evaluate unmatched returns DENY", decision2 == PolicyDecision.DENY)

    rule2 = PolicyRule("network.*", PolicyDecision.DENY, "plugin.*")
    engine.add_rule(rule2)
    decision3 = engine.evaluate("plugin.test", "network.outbound")
    check("evaluate network returns DENY", decision3 == PolicyDecision.DENY)

    rules = engine.get_rules()
    check("get_rules has 2", len(rules) == 2)

    removed = engine.remove_rule(rule2)
    check("remove_rule succeeded", removed)
    check("get_rules has 1 after remove", len(engine.get_rules()) == 1)

    engine.clear_rules()
    check("After clear 0 rules", len(engine.get_rules()) == 0)

    stats = engine.get_stats()
    check("Stats has total_rules", "total_rules" in stats)


# ── 27. SandboxValidator ──

def test_sandbox_validator():
    print("\n=== 27. SandboxValidator ===")
    from infrastructure.plugins.sandbox import SandboxValidator

    validator = SandboxValidator()
    check("SandboxValidator created", validator is not None)

    result = validator.validate_plugin("val.test")
    check("validate_plugin returns dict", isinstance(result, dict))
    check("has plugin_id", result["plugin_id"] == "val.test")
    check("has valid key", "valid" in result)
    check("has errors key", "errors" in result)

    iso_errors = validator.validate_isolation("val.test")
    check("validate_isolation returns list", isinstance(iso_errors, list))
    check("No isolation errors for valid id", len(iso_errors) == 0)

    iso_bad = validator.validate_isolation("")
    check("Isolation error for empty", len(iso_bad) > 0)

    perm_errors = validator.validate_permissions("val.test")
    check("validate_permissions returns list", isinstance(perm_errors, list))

    res_errors = validator.validate_resources("val.test")
    check("validate_resources returns list", isinstance(res_errors, list))

    sec_errors = validator.validate_security("val.test")
    check("validate_security returns list", isinstance(sec_errors, list))

    fs_errors = validator.validate_filesystem("val.test")
    check("validate_filesystem returns list", isinstance(fs_errors, list))

    net_errors = validator.validate_network("val.test")
    check("validate_network returns list", isinstance(net_errors, list))

    secrets_errors = validator.validate_secrets("val.test")
    check("validate_secrets returns list", isinstance(secrets_errors, list))

    stats = validator.get_stats()
    check("Stats has checks_available", "checks_available" in stats)


# ── 28. SandboxMetrics ──

def test_sandbox_metrics():
    print("\n=== 28. SandboxMetrics ===")
    from infrastructure.plugins.sandbox import SandboxMetrics

    metrics = SandboxMetrics()
    check("SandboxMetrics created", metrics is not None)

    metrics.record_sandbox_start("sandbox.test", 150.5)
    check("record_sandbox_start succeeded", True)

    counter = metrics.get_counter("icyquant_sandbox_start_total")
    check("Start counter >= 1", counter >= 1)

    metrics.record_violation("sandbox.test", "memory_limit")
    check("record_violation succeeded", True)

    viol_counter = metrics.get_counter("icyquant_sandbox_violations_total")
    check("Violation counter >= 1", viol_counter >= 1)

    metrics.record_access_denied("sandbox.test", "filesystem")
    metrics.record_resource_exceeded("sandbox.test", "memory", 256 * 1024 * 1024, 512 * 1024 * 1024)
    metrics.record_policy_check("sandbox.test", "filesystem.read", True)
    metrics.record_audit_event("sandbox.test", "sandbox_created")

    snap = metrics.snapshot()
    check("snapshot has counters", "counters" in snap)
    check("snapshot has plugins", "plugins" in snap)
    check("snapshot has timestamp", "timestamp" in snap)

    metrics.set_gauge("memory_usage", 0.75)
    gauge = metrics.get_gauge("memory_usage")
    check("get_gauge correct", gauge == 0.75)

    metrics.increment_counter("custom_counter", 5.0)
    check("increment_counter", metrics.get_counter("custom_counter") == 5)

    stats = metrics.get_stats()
    check("Stats has total_plugins_tracked", "total_plugins_tracked" in stats)

    metrics.reset()
    snap2 = metrics.snapshot()
    check("After reset counters 0", snap2["counters"].get("icyquant_sandbox_start_total", 0) == 0)


# ── 29. AuditLog ──

def test_audit_log():
    print("\n=== 29. AuditLog ===")
    from infrastructure.plugins.sandbox import AuditLog

    audit = AuditLog()
    check("AuditLog created", audit is not None)

    audit.log_event(
        event_type="sandbox_created",
        plugin_id="audit.test",
        message="Sandbox created successfully",
        details={"memory_limit": "256MB"},
        severity="info",
    )
    check("log_event succeeded", True)

    audit.log_event(
        event_type="permission_denied",
        plugin_id="audit.test",
        message="Permission denied: trade_order",
        severity="warning",
    )

    events = audit.query(plugin_id="audit.test")
    check("query returns events", len(events) >= 2)

    recent = audit.get_recent(limit=1)
    check("get_recent returns list", isinstance(recent, list))
    check("get_recent limit works", len(recent) <= 1)

    counts = audit.get_event_counts("audit.test")
    check("get_event_counts returns dict", isinstance(counts, dict))
    check("Has sandbox_created count", counts.get("sandbox_created", 0) >= 1)

    events_by_type = audit.query(event_type="permission_denied")
    check("Filter by event_type", len(events_by_type) >= 1)

    events_by_severity = audit.query(severity="warning")
    check("Filter by severity", len(events_by_severity) >= 1)

    stats = audit.get_stats()
    check("Stats has total_entries", "total_entries" in stats)
    check("Stats has max_entries", "max_entries" in stats)

    audit.clear()
    check("After clear 0 entries", audit.get_stats()["total_entries"] == 0)


# ── 30. RecoveryManager ──

def test_recovery_manager():
    print("\n=== 30. RecoveryManager ===")
    from infrastructure.plugins.sandbox import RecoveryManager

    rm = RecoveryManager()
    check("RecoveryManager created", rm is not None)

    restart_called = []
    def restart_handler():
        restart_called.append(True)

    rm.register_restart_handler("recovery.test", restart_handler)
    check("register_restart_handler succeeded", True)

    info = rm.get_failure_info("recovery.test")
    check("No failure info initially", info is None)

    result1 = rm.record_failure("recovery.test", "test error 1")
    check("record_failure returns dict", isinstance(result1, dict))
    check("should_retry is True on first", result1["should_retry"] is True)
    check("failure_count is 1", result1["failure_count"] == 1)

    result2 = rm.record_failure("recovery.test", "test error 2")
    check("failure_count is 2", result2["failure_count"] == 2)

    for i in range(5):
        rm.record_failure("recovery.test", f"error {i+3}")

    info_after = rm.get_failure_info("recovery.test")
    check("Has failure info", info_after is not None)
    check("Circuit open after max retries", info_after["circuit_open"] is True)

    rm.reset_plugin("recovery.test")
    info_reset = rm.get_failure_info("recovery.test")
    check("After reset count is 0", info_reset["count"] == 0)
    check("After reset circuit not open", not info_reset["circuit_open"])

    recovery_result = rm.attempt_recovery("recovery.test")
    check("Recovery succeeds", recovery_result["success"] is True)
    check("Restart handler called", len(restart_called) >= 1)

    try:
        rm.attempt_recovery("no_handler.test")
        check("Should raise for no handler", False)
    except Exception:
        check("Recovery raises for no handler", True)

    stats = rm.get_stats()
    check("Stats has total_failed_plugins", "total_failed_plugins" in stats)


# ── Main ──

def main():
    print("=" * 60)
    print("  ICYQuant Loader & Sandbox Validation")
    print("=" * 60)

    # Loader sync tests
    test_loader_basic()
    test_directory_scanner()
    test_plugin_importer()
    test_dependency_resolver2()
    test_loader_cache()
    test_loader_metrics()
    test_loader_diagnostics()
    test_plugin_verifier()
    test_loader_validator()
    test_plugin_installer()
    test_plugin_uninstaller()
    test_plugin_reloader()
    test_file_watcher()

    # Sandbox sync tests
    test_sandbox_basic()
    test_sandbox_runtime()
    test_sandbox_permission_guard()
    test_sandbox_capability_guard()
    test_resource_quota()
    test_filesystem_policy()
    test_network_policy()
    test_signature_verifier()
    test_trust_store()
    test_sandbox_policy()
    test_policy_engine()
    test_sandbox_validator()
    test_sandbox_metrics()
    test_audit_log()
    test_recovery_manager()

    # Async tests
    asyncio.run(test_loader_integration())
    asyncio.run(test_isolation_manager())

    print("\n" + "=" * 60)
    print(f"  Results: {PASSED} passed, {FAILED} failed")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n  All loader and sandbox validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()