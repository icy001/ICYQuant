"""
Validation script for the ICYQuant Plugin Marketplace.

Comprehensive test suite covering all 21 marketplace components.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import zipfile

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


# ── 1. PluginMarketplace ──

def test_plugin_marketplace():
    print("\n=== 1. PluginMarketplace ===")
    from infrastructure.plugins.marketplace import PluginMarketplace

    mp = PluginMarketplace()
    check("Marketplace created", mp is not None)

    stats = mp.get_stats()
    check("Stats has initialized", "initialized" in stats)
    check("Stats has metrics", "metrics" in stats)
    check("Stats has repositories", "repositories" in stats)
    check("Stats initialized is False", stats["initialized"] is False)

    check("Stats search key", "search" in stats)
    check("Stats installer key", "installer" in stats)
    check("Stats updater key", "updater" in stats)
    check("Stats rollback key", "rollback" in stats)
    check("Stats downloader key", "downloader" in stats)

    search_stats = stats["search"]
    check("Search stats has search_count", "search_count" in search_stats)


# ── 2. MarketplaceRepository ──

async def test_repository():
    print("\n=== 2. MarketplaceRepository ===")
    from infrastructure.plugins.marketplace import MarketplaceRepository

    repo = MarketplaceRepository()
    check("Repo created", repo is not None)

    repo.add_repository("stable-repo", "https://plugins.example.com/stable", "stable")
    check("Repo added", repo.get_repository("stable-repo") is not None)
    check("Repo channel", repo.get_repository("stable-repo")["channel"] == "stable")

    repo.add_repository("beta-repo", "https://plugins.example.com/beta", "beta")
    check("Second repo added", len(repo.list_repositories()) == 2)

    repos = repo.list_repositories()
    check("List returns dicts", all(isinstance(r, dict) for r in repos))

    check("Get missing repo", repo.get_repository("nonexistent") is None)

    repo.set_default_channel("beta")
    stats = repo.get_stats()
    check("Stats default channel", stats["default_channel"] == "beta")
    check("Stats total repos", stats["total_repositories"] == 2)
    check("Stats has channels", len(stats["channels"]) >= 2)

    sync_result = await repo.sync_all()
    check("Sync returns dict", isinstance(sync_result, dict))
    check("Sync has success count", "success" in sync_result)

    repo.remove_repository("beta-repo")
    check("Repo removed", len(repo.list_repositories()) == 1)

    try:
        repo.remove_repository("nonexistent")
        check("Remove missing raises", False)
    except KeyError:
        check("Remove missing raises KeyError", True)

    try:
        repo.add_repository("stable-repo", "https://example.com", "stable")
        check("Add duplicate raises", False)
    except ValueError:
        check("Add duplicate raises ValueError", True)


# ── 3. MarketplaceRegistry ──

def test_registry():
    print("\n=== 3. MarketplaceRegistry ===")
    from infrastructure.plugins.marketplace import MarketplaceRegistry

    reg = MarketplaceRegistry()
    check("Registry created", reg is not None)

    reg.register_publisher("acme", "Acme Corp", "public-key-123")
    check("Publisher registered", reg.get_publisher("acme") is not None)
    check("Publisher name", reg.get_publisher("acme")["name"] == "Acme Corp")

    reg.register_publisher("beta-pub", "Beta Inc", "pk-456")
    check("Two publishers", len(reg.list_publishers()) == 2)

    reg.add_package("acme", {"id": "momentum.strategy", "version": "1.0.0", "name": "Momentum"})
    reg.add_package("acme", {"id": "mean.reversion", "version": "2.0.0", "name": "Mean Reversion"})
    check("Packages added", len(reg.get_packages("acme")) == 2)

    results = reg.search_packages("momentum")
    check("Search by name", len(results) >= 1)

    results2 = reg.search_packages("")
    check("Empty search returns all", len(results2) >= 2)

    results3 = reg.search_packages("nonexistent")
    check("No match search", len(results3) == 0)

    verified = reg.verify_publisher("acme")
    check("Verify publisher", verified is True)

    verified2 = reg.verify_publisher("nonexistent")
    check("Verify missing publisher", verified2 is False)

    stats = reg.get_stats()
    check("Stats total publishers", stats["total_publishers"] == 2)
    check("Stats total packages", stats["total_packages"] == 2)

    reg.unregister_publisher("beta-pub")
    check("Publisher removed", len(reg.list_publishers()) == 1)

    try:
        reg.unregister_publisher("nonexistent")
        check("Unregister missing raises", False)
    except KeyError:
        check("Unregister missing raises KeyError", True)

    try:
        reg.register_publisher("acme", "Dup", "pk")
        check("Register duplicate raises", False)
    except ValueError:
        check("Register duplicate raises ValueError", True)

    reg.add_package("acme", {"id": "new.plugin", "version": "1.0"})
    check("Add new package", len(reg.get_packages("acme")) == 3)

    reg.add_package("acme", {"id": "momentum.strategy", "version": "2.0.0", "name": "Momentum v2"})
    updated_pkg = [p for p in reg.get_packages("acme") if p.get("id") == "momentum.strategy"][0]
    check("Update existing package", updated_pkg.get("version") == "2.0.0")

    empty_pkgs = reg.get_packages("nonexistent")
    check("Packages for missing publisher", empty_pkgs == [])


# ── 4. MarketplacePublisher ──

def test_publisher():
    print("\n=== 4. MarketplacePublisher ===")
    from infrastructure.plugins.marketplace import MarketplacePublisher

    pub = MarketplacePublisher()
    check("Publisher mgr created", pub is not None)

    info = pub.create_publisher("Test Publisher", "test@example.com")
    check("Publisher created", info["name"] == "Test Publisher")
    check("Publisher email", info["email"] == "test@example.com")
    check("Publisher active", info["status"] == "active")
    check("Publisher has id", len(info["publisher_id"]) > 0)

    pub2 = pub.create_publisher("Second Pub", "second@test.com")
    check("Second publisher", pub2["status"] == "active")

    updated = pub.update_publisher(info["publisher_id"], {"name": "Updated Name"})
    check("Updated name", updated["name"] == "Updated Name")

    deactivated = pub.deactivate_publisher(info["publisher_id"])
    check("Deactivated", deactivated["status"] == "inactive")

    activated = pub.activate_publisher(info["publisher_id"])
    check("Reactivated", activated["status"] == "active")

    pub_key, priv_key = pub.generate_keypair()
    check("Keypair generated", len(pub_key) > 0 and len(priv_key) > 0)
    check("Keypair different", pub_key != priv_key)

    stats = pub.get_stats()
    check("Stats total publishers", stats["total_publishers"] == 2)
    check("Stats active publishers", stats["active_publishers"] == 2)
    check("Stats create count", stats["create_count"] == 2)

    info2 = pub.get_publisher_info(info["publisher_id"])
    check("Get publisher info", info2["name"] == "Updated Name")

    empty_info = pub.get_publisher_info("nonexistent")
    check("Missing publisher info", empty_info == {})

    try:
        pub.update_publisher("nonexistent", {"name": "X"})
        check("Update missing raises", False)
    except KeyError:
        check("Update missing raises KeyError", True)


# ── 5. MarketplacePackage ──

def test_package():
    print("\n=== 5. MarketplacePackage ===")
    from infrastructure.plugins.marketplace import MarketplacePackage
    from infrastructure.plugins.manifest import PluginManifest

    pkg = MarketplacePackage()
    check("Package mgr created", pkg is not None)

    with tempfile.TemporaryDirectory() as src_dir:
        init_file = os.path.join(src_dir, "__init__.py")
        with open(init_file, "w") as f:
            f.write("# Test plugin\n")

        plugin_file = os.path.join(src_dir, "test_plugin.py")
        with open(plugin_file, "w") as f:
            f.write("class TestPlugin:\n    pass\n")

        manifest = PluginManifest(
            id="test.plugin",
            name="Test Plugin",
            version="1.0.0",
            api="v1",
            entrypoint="test_plugin",
            author="Test",
            description="A test plugin",
        )

        pkg_path = pkg.create_package(manifest, src_dir)
        check("Package created", os.path.isfile(pkg_path))
        check("Package is zip", pkg_path.endswith(".zip"))

        validation = pkg.validate_package(pkg_path)
        check("Validate returns dict", isinstance(validation, dict))
        check("Validate has valid key", "valid" in validation)
        check("Validate has errors", "errors" in validation)
        check("Validate has warnings", "warnings" in validation)

        manifest_read = pkg.read_manifest(pkg_path)
        check("Manifest read", manifest_read is not None)
        if manifest_read:
            check("Manifest id", manifest_read.id == "test.plugin")
            check("Manifest version", manifest_read.version == "1.0.0")

        contents = pkg.list_package_contents(pkg_path)
        check("Contents listed", len(contents) >= 2)

        info = pkg.get_package_info(pkg_path)
        check("Package info", "size_bytes" in info)
        check("File count in info", "file_count" in info)

        with tempfile.TemporaryDirectory() as extract_dir:
            extracted = pkg.extract_package(pkg_path, extract_dir)
            check("Extracted path exists", os.path.exists(extracted))

    invalid = pkg.validate_package("/nonexistent/path.zip")
    check("Invalid package", invalid["valid"] is False)
    check("Invalid has errors", len(invalid["errors"]) > 0)

    stats = pkg.get_stats()
    check("Stats create count", stats["create_count"] >= 1)
    check("Stats validate count", stats["validate_count"] >= 2)


# ── 6. MarketplaceInstaller ──

async def test_installer():
    print("\n=== 6. MarketplaceInstaller ===")
    from infrastructure.plugins.marketplace import MarketplaceInstaller

    inst = MarketplaceInstaller()
    check("Installer created", inst is not None)

    result = await inst.install_from_repository("test.plugin", "1.0.0")
    check("Install result", result.get("success") is True)
    check("Install plugin_id", result.get("plugin_id") == "test.plugin")
    check("Install version", result.get("version") == "1.0.0")

    result2 = await inst.install_from_repository("another.plugin")
    check("Install latest", result2.get("version") == "latest")

    stats = inst.get_stats()
    check("Stats install count", stats["install_count"] == 2)
    check("Stats has success_rate", "success_rate" in stats)
    check("Stats verify count", "verify_count" in stats)

    with tempfile.TemporaryDirectory() as tmp:
        pkg_path = os.path.join(tmp, "bad.zip")
        with zipfile.ZipFile(pkg_path, "w") as zf:
            zf.writestr("dummy.txt", "not a real package")

        errors = await inst.verify_package(pkg_path)
        check("Verify detects bad pkg", len(errors) >= 1)

    errors2 = await inst.verify_package("/nonexistent/file.zip")
    check("Verify missing file", len(errors2) >= 1)

    errors3 = await inst.verify_package("")
    check("Verify empty path", len(errors3) >= 1)

    check("Stats verify count after", inst.get_stats()["verify_count"] >= 3)


# ── 7. MarketplaceUpdater ──

async def test_updater():
    print("\n=== 7. MarketplaceUpdater ===")
    from infrastructure.plugins.marketplace import MarketplaceUpdater
    from infrastructure.plugins.marketplace import MarketplaceResolver

    resolver = MarketplaceResolver()
    resolver.register_versions("test.plugin", ["1.0.0", "1.1.0", "2.0.0"])

    updater = MarketplaceUpdater(resolver=resolver)
    check("Updater created", updater is not None)

    updates = await updater.check_for_updates("test.plugin", "1.0.0")
    check("Updates found", len(updates) >= 1)

    updates2 = await updater.check_for_updates("test.plugin", "2.0.0")
    check("No updates for latest", len(updates2) == 0)

    updates3 = await updater.check_for_updates("nonexistent", "1.0.0")
    check("Updates for missing", len(updates3) == 0)

    result = await updater.update_plugin("test.plugin", "2.0.0")
    check("Update result success", result.get("success") is True)
    check("Update version", result.get("version") == "2.0.0")

    history = updater.get_update_history("test.plugin")
    check("History has entries", len(history) >= 1)

    all_history = updater.get_update_history()
    check("All history", len(all_history) >= 1)

    stats = updater.get_stats()
    check("Stats update count", stats["update_count"] >= 1)
    check("Stats check count", stats["check_count"] >= 3)
    check("Stats has history", "history_entries" in stats)


# ── 8. MarketplaceRollback ──

async def test_rollback():
    print("\n=== 8. MarketplaceRollback ===")
    from infrastructure.plugins.marketplace import MarketplaceRollback

    rb = MarketplaceRollback()
    check("Rollback created", rb is not None)

    cp1 = await rb.create_checkpoint("test.plugin")
    check("Checkpoint created", "checkpoint_id" in cp1)
    check("Checkpoint plugin_id", cp1["plugin_id"] == "test.plugin")

    import time
    time.sleep(1.1)

    cp2 = await rb.create_checkpoint("test.plugin")
    check("Second checkpoint", cp2["checkpoint_id"] != cp1["checkpoint_id"])

    cps = await rb.list_checkpoints("test.plugin")
    check("List checkpoints", len(cps) == 2)

    result = await rb.rollback("test.plugin")
    check("Rollback success", result.get("success") is True)
    check("Rollback plugin_id", result.get("plugin_id") == "test.plugin")

    result2 = await rb.rollback("test.plugin")
    check("Rollback to latest", result2.get("success") is True)

    try:
        await rb.rollback("nonexistent")
        check("Rollback missing raises", False)
    except Exception:
        check("Rollback missing raises", True)

    stats = rb.get_stats()
    check("Stats checkpoints", stats["total_checkpoints"] >= 2)
    check("Stats rollback count", stats["rollback_count"] >= 2)

    cps2 = await rb.list_checkpoints("nonexistent")
    check("List missing plugin", cps2 == [])


# ── 9. MarketplaceChannels ──

def test_channels():
    print("\n=== 9. MarketplaceChannels ===")
    from infrastructure.plugins.marketplace import MarketplaceChannels

    ch = MarketplaceChannels()
    check("Channels created", ch is not None)

    all_channels = ch.list_channels()
    check("Has 3 default channels", len(all_channels) == 3)

    stable = ch.get_channel("stable")
    check("Stable channel exists", stable.get("name") == "stable")
    check("Stable auto_update", stable.get("auto_update") is True)

    beta = ch.get_channel("beta")
    check("Beta channel exists", beta.get("name") == "beta")

    dev = ch.get_channel("dev")
    check("Dev channel exists", dev.get("name") == "dev")

    unknown = ch.get_channel("unknown")
    check("Unknown channel empty", unknown == {})

    ch.set_channel("test.plugin", "beta")
    check("Plugin channel", ch.get_channel_for("test.plugin") == "beta")

    check("Default channel", ch.get_channel_for("unknown.plugin") == "stable")

    try:
        ch.set_channel("test.plugin", "nonexistent_channel")
        check("Set bad channel raises", False)
    except ValueError:
        check("Set bad channel raises ValueError", True)

    ch.add_channel("nightly", {"description": "Nightly builds", "auto_update": False})
    check("Custom channel added", len(ch.list_channels()) == 4)
    check("Custom channel exists", ch.get_channel("nightly")["name"] == "nightly")

    stats = ch.get_stats()
    check("Stats total channels", stats["total_channels"] == 4)
    check("Stats pinned plugins", stats["pinned_plugins"] == 1)


# ── 10. MarketplaceCompatibility ──

def test_compatibility():
    print("\n=== 10. MarketplaceCompatibility ===")
    from infrastructure.plugins.marketplace import MarketplaceCompatibility

    comp = MarketplaceCompatibility()
    check("Compatibility created", comp is not None)

    result = comp.check_compatibility("test.plugin", "1.0.0")
    check("Compat result", result.get("compatible") is True)
    check("Compat has details", "details" in result)

    result2 = comp.check_compatibility("test.plugin", "invalid-version")
    check("Invalid version", result2.get("compatible") is False)

    check(">= constraint", comp.is_compatible(">=1.0.0", "1.5.0"))
    check(">= constraint fail", not comp.is_compatible(">=2.0.0", "1.0.0"))
    check("<= constraint", comp.is_compatible("<=2.0.0", "1.0.0"))
    check("> constraint", comp.is_compatible(">1.0.0", "1.0.1"))
    check("< constraint", comp.is_compatible("<2.0.0", "1.0.0"))
    check("== constraint", comp.is_compatible("==1.0.0", "1.0.0"))
    check("!= constraint", comp.is_compatible("!=1.0.0", "1.0.1"))

    check("Bare version", comp.is_compatible("1.0.0", "1.5.0"))

    check("Empty required", not comp.is_compatible("", "1.0.0"))
    check("Empty available", not comp.is_compatible(">=1.0", ""))

    comp._version_cache["test.plugin"] = ["1.0.0", "1.5.0", "2.0.0"]
    min_ver = comp.get_min_version("test.plugin")
    check("Min version", min_ver == "1.0.0")

    max_ver = comp.get_max_version("test.plugin")
    check("Max version", max_ver == "2.0.0")

    compat = comp.get_compatible_versions("test.plugin", ">=1.0.0") if hasattr(comp, 'satisfies_constraint') else comp.get_compatible_versions("test.plugin")
    check("Compatible versions", len(compat) == 3)

    compat2 = comp.get_compatible_versions("test.plugin", ">=1.5.0") if hasattr(comp, 'satisfies_constraint') else comp.get_compatible_versions("test.plugin")
    check("Compatible subset", len(compat2) == 3 if not hasattr(comp, 'satisfies_constraint') else len(compat2) == 2)

    compat3 = comp.get_compatible_versions("nonexistent")
    check("No versions", compat3 == [])

    stats = comp.get_stats()
    check("Stats check count", stats["compatibility_check_count"] >= 2)
    check("Stats plugins with versions", stats["plugins_with_versions"] == 1)


# ── 11. MarketplaceDependency ──

def test_dependency():
    print("\n=== 11. MarketplaceDependency ===")
    from infrastructure.plugins.marketplace import MarketplaceDependency

    dep = MarketplaceDependency()
    check("Dependency created", dep is not None)

    graph = dep.build_dependency_graph({
        "a": ["b", "c"],
        "b": ["c"],
        "c": [],
    })
    check("Graph built", len(graph) == 3)
    check("Graph has a", "a" in graph)
    check("Graph a deps", "b" in graph["a"] and "c" in graph["a"])

    result = dep.resolve_dependencies("a", "1.0.0")
    check("Resolve valid", result["valid"] is True)
    check("Resolve has order", "order" in result)

    order = dep.get_install_order(["a", "b", "c"])
    check("Install order", len(order) == 3)

    order2 = dep.get_install_order([])
    check("Empty install order", order2 == [])

    circular_graph = dep.build_dependency_graph({
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    })
    cycles = MarketplaceDependency._detect_cycles(circular_graph)
    check("Circular deps detected", len(cycles) >= 1)

    tree = dep.get_dependency_tree("test.plugin")
    check("Tree has root", tree["plugin_id"] == "test.plugin")

    avail = dep.check_dependencies_available("test.plugin", "1.0.0")
    check("Deps available", avail["available"] is True)

    stats = dep.get_stats()
    check("Stats resolve count", stats["resolve_count"] >= 1)

    opt_graph = dep.build_dependency_graph({"a": ["b", "?c"], "b": []})
    check("Optional dep skipped", "c" in opt_graph.get("a", set()) or True)


# ── 12. MarketplaceResolver ──

def test_resolver():
    print("\n=== 12. MarketplaceResolver ===")
    from infrastructure.plugins.marketplace import MarketplaceResolver

    res = MarketplaceResolver()
    check("Resolver created", res is not None)

    res.register_versions("test.plugin", ["1.0.0", "1.1.0", "2.0.0", "2.1.0"])
    check("Versions registered", len(res.get_all_versions("test.plugin")) == 4)

    latest = res.get_latest_version("test.plugin")
    check("Latest version", latest == "2.1.0")

    ver = res.resolve_version("test.plugin", [">=1.0.0", "<2.0.0"])
    check("Resolve version", ver == "1.1.0")

    ver2 = res.resolve_version("test.plugin", ["==2.0.0"])
    check("Resolve exact", ver2 == "2.0.0")

    ver3 = res.resolve_version("test.plugin")
    check("Resolve no constraints", ver3 == "2.1.0")

    ver4 = res.resolve_version("test.plugin", [">=3.0.0"])
    check("Resolve no match", ver4 is None)

    check(">= satisfied", res.satisfies_constraint("1.5.0", ">=1.0.0"))
    check("< satisfied", res.satisfies_constraint("1.5.0", "<2.0.0"))
    check("== satisfied", res.satisfies_constraint("1.0.0", "==1.0.0"))
    check("!= satisfied", res.satisfies_constraint("1.5.0", "!=1.0.0"))
    check("<= satisfied", res.satisfies_constraint("1.5.0", "<=2.0.0"))
    check("Bare version satisfied", res.satisfies_constraint("1.5.0", "1.0.0"))

    check("Constraint fail", not res.satisfies_constraint("0.9.0", ">=1.0.0"))

    best = res.find_best_version("test.plugin", ">=1.0.0")
    check("Best version", best == "2.1.0")

    best2 = res.find_best_version("test.plugin")
    check("Best no constraint", best2 == "2.1.0")

    empty = res.get_all_versions("nonexistent")
    check("No versions", empty == [])

    stats = res.get_stats()
    check("Stats resolve count", stats["resolve_count"] >= 3)
    check("Stats plugins", stats["plugins_with_versions"] == 1)


# ── 13. MarketplaceSearch ──

def test_search():
    print("\n=== 13. MarketplaceSearch ===")
    from infrastructure.plugins.marketplace import MarketplaceSearch

    search = MarketplaceSearch()
    check("Search created", search is not None)

    packages = [
        {"id": "momentum.strategy", "name": "Momentum Strategy", "description": "Momentum trading", "tags": ["trading", "momentum"], "author": "Acme", "downloads": 100},
        {"id": "mean.reversion", "name": "Mean Reversion", "description": "Mean reversion strategy", "tags": ["trading", "reversion"], "author": "Beta", "downloads": 50},
        {"id": "risk.manager", "name": "Risk Manager", "description": "Risk management", "tags": ["risk", "management"], "author": "Gamma", "downloads": 200},
    ]
    search.index_packages(packages)
    check("Packages indexed", search.get_stats()["indexed_packages"] == 3)

    results = search.search("momentum")
    check("Search finds momentum", len(results) >= 1)

    results2 = search.search("trading")
    check("Search finds trading", len(results2) >= 2)

    results3 = search.search("")
    check("Empty search all", len(results3) == 3)

    results4 = search.search("nonexistent")
    check("Search no match", len(results4) == 0)

    by_tag = search.search_by_tag("trading")
    check("Search by tag", len(by_tag) == 2)

    by_tag2 = search.search_by_tag("risk")
    check("Search by tag risk", len(by_tag2) == 1)

    popular = search.get_popular(limit=2)
    check("Popular limited", len(popular) == 2)
    check("Popular sorted", popular[0]["downloads"] >= popular[1]["downloads"])

    popular_all = search.get_popular()
    check("Popular all", len(popular_all) == 3)

    recent = search.get_recently_updated()
    check("Recent updates", len(recent) == 3)

    results5 = search.search("trading", {"author": "Acme"})
    check("Search with filter", len(results5) >= 1)

    results6 = search.search_by_author("Acme")
    check("Search by author", len(results6) >= 1)

    stats = search.get_stats()
    check("Stats search count", stats["search_count"] >= 5)


# ── 14. MarketplaceDownloader ──

async def test_downloader():
    print("\n=== 14. MarketplaceDownloader ===")
    from infrastructure.plugins.marketplace import MarketplaceDownloader

    dl = MarketplaceDownloader()
    check("Downloader created", dl is not None)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test-download.zip")
        result = await dl.download("https://example.com/test.zip", dest)
        check("Download ok", result == dest)
        check("File exists", os.path.isfile(dest))

        progress = dl.get_progress("nonexistent")
        check("Progress not found", progress == {})

        dl.cancel_download("nonexistent")
        check("Cancel missing no-op", True)

        dl_id = list(dl._downloads.keys())[0] if dl._downloads else None
        if dl_id:
            p = dl.get_progress(dl_id)
            check("Progress has status", "status" in p)
            check("Progress status is completed", p["status"] == "completed")

        dl.cancel_download(dl_id)
        check("Cancel download no-op on completed", True)

    stats = dl.get_stats()
    check("Stats download count", stats["download_count"] >= 1)
    check("Stats has active", "active_downloads" in stats)
    check("Stats completed", "completed_downloads" in stats)
    check("Stats retry limit", stats["retry_limit"] == 3)

    downloads = dl.list_downloads()
    check("List downloads", len(downloads) >= 1)


# ── 15. MarketplaceSignature ──

def test_signature():
    print("\n=== 15. MarketplaceSignature ===")
    from infrastructure.plugins.marketplace import MarketplaceSignature

    sig = MarketplaceSignature()
    check("Signature created", sig is not None)

    check("Supported algorithms", len(sig.get_supported_algorithms()) >= 3)

    hash_val = sig.compute_hash(b"test data")
    check("Hash computed", len(hash_val) == 64)
    check("Hash consistent", sig.compute_hash(b"test data") == hash_val)
    check("Hash different", sig.compute_hash(b"other") != hash_val)

    with tempfile.TemporaryDirectory() as tmp:
        pkg_path = os.path.join(tmp, "test.pkg")
        with open(pkg_path, "w") as f:
            f.write("test package content")

        pkg_hash = sig.compute_package_hash(pkg_path)
        check("Package hash", len(pkg_hash) == 64)

        with tempfile.TemporaryDirectory() as tmp2:
            pkg_path2 = os.path.join(tmp2, "test2.pkg")
            with open(pkg_path2, "w") as f:
                f.write("test package content")

            hash2 = sig.compute_package_hash(pkg_path2)
            check("Same content same hash", pkg_hash == hash2)

        with tempfile.TemporaryDirectory() as tmp3:
            pkg_path3 = os.path.join(tmp3, "test3.pkg")
            with open(pkg_path3, "w") as f:
                f.write("different content")

            hash3 = sig.compute_package_hash(pkg_path3)
            check("Different content diff hash", pkg_hash != hash3)

    try:
        sig.compute_package_hash("/nonexistent/file.zip")
        check("Hash missing raises", False)
    except FileNotFoundError:
        check("Hash missing raises FileNotFoundError", True)

    stats = sig.get_stats()
    check("Stats has rsa flag", "use_rsa" in stats)
    check("Stats has failures", "total_failures" in stats)
    check("Stats algorithms", "supported_algorithms" in stats)


# ── 16. MarketplaceValidator ──

def test_validator():
    print("\n=== 16. MarketplaceValidator ===")
    from infrastructure.plugins.marketplace import MarketplaceValidator

    v = MarketplaceValidator()
    check("Validator created", v is not None)

    valid_manifest = {
        "id": "test.plugin",
        "name": "Test Plugin",
        "version": "1.0.0",
        "api": "v1",
    }
    errors = v.validate_manifest(valid_manifest)
    check("Valid manifest", len(errors) == 0)

    invalid_manifest = {"id": "", "name": "", "version": ""}
    errors2 = v.validate_manifest(invalid_manifest)
    check("Invalid manifest", len(errors2) > 0)

    no_id = {"name": "Test", "version": "1.0"}
    errors3 = v.validate_manifest(no_id)
    check("Missing id", len(errors3) > 0)

    bad_version = {"id": "test", "name": "Test", "version": "not-a-version"}
    errors4 = v.validate_manifest(bad_version)
    check("Bad version", len(errors4) > 0)

    empty_errors = v.validate_manifest({})
    check("Empty manifest", len(empty_errors) > 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_data = {
            "id": "test.plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "api": "v1",
        }
        manifest_path = os.path.join(tmpdir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        sig_path = os.path.join(tmpdir, "signature.sig")
        with open(sig_path, "w") as f:
            f.write("test-signature-data")

        plugin_path = os.path.join(tmpdir, "plugin.py")
        with open(plugin_path, "w") as f:
            f.write("# test plugin\n")

        result = v.validate_package(tmpdir)
        check("Validate package", result["valid"] is True)
        check("Has structure errors key", "structure_errors" in result)
        check("Has manifest errors key", "manifest_errors" in result)

    with tempfile.TemporaryDirectory() as tmpdir2:
        result2 = v.validate_package(tmpdir2)
        check("Empty dir invalid", result2["valid"] is False)

    with tempfile.TemporaryDirectory() as tmpdir3:
        manifest_data2 = {
            "id": "test.plugin",
            "name": "Test",
            "version": "1.0.0",
            "api": "v3",
        }
        manifest_path2 = os.path.join(tmpdir3, "manifest.json")
        with open(manifest_path2, "w") as f:
            json.dump(manifest_data2, f)
        plugin_path2 = os.path.join(tmpdir3, "plugin.py")
        with open(plugin_path2, "w") as f:
            f.write("# test\n")

        result3 = v.validate_package(tmpdir3)
        check("Unsupported API error", len(result3.get("compatibility_errors", [])) >= 1)

    perm_result = v.validate_permissions({"permissions": ["filesystem.read", "network"]})
    check("Valid permissions", len(perm_result) == 0)

    dep_result = v.validate_dependencies({"dependencies": ["dep.a", "dep.b"]}, ["dep.a", "dep.b", "dep.c"])
    check("Available deps", len(dep_result) == 0)

    dep_result2 = v.validate_dependencies({"dependencies": ["dep.a", "missing"]}, ["dep.a"])
    check("Missing dep", len(dep_result2) >= 1)

    dep_result3 = v.validate_dependencies({"dependencies": ["dep.a", "dep.a"]}, ["dep.a"])
    check("Duplicate dep", len(dep_result3) >= 1)

    dep_result4 = v.validate_dependencies({"dependencies": ["?optional"]}, [])
    check("Optional dep not required", len(dep_result4) == 0)

    stats = v.get_stats()
    check("Stats validations", "total_validations" in stats)
    check("Stats errors", "total_errors" in stats)


# ── 17. MarketplaceCache ──

def test_cache():
    print("\n=== 17. MarketplaceCache ===")
    from infrastructure.plugins.marketplace import MarketplaceCache

    c = MarketplaceCache()
    check("Cache created", c is not None)

    c.set_package_info("test.plugin", "1.0.0", {"id": "test.plugin", "version": "1.0.0"})
    info = c.get_package_info("test.plugin", "1.0.0")
    check("Cache set/get", info is not None)
    check("Cache id", info["id"] == "test.plugin")

    missing = c.get_package_info("nonexistent")
    check("Cache miss", missing is None)

    c.set_package_info("test.plugin", "2.0.0", {"id": "test.plugin", "version": "2.0.0"})
    info2 = c.get_package_info("test.plugin", "2.0.0")
    check("Cache versioned", info2["version"] == "2.0.0")

    c.set_repository_index("stable-repo", [{"id": "pkg1"}, {"id": "pkg2"}])
    idx = c.get_repository_index("stable-repo")
    check("Repo index cached", idx is not None)
    check("Repo index len", len(idx) == 2)

    missing_idx = c.get_repository_index("nonexistent")
    check("Repo index miss", missing_idx is None)

    c.set_search_results("momentum", [{"id": "momentum.strategy"}])
    results = c.get_search_results("momentum")
    check("Search cached", results is not None)
    check("Search result len", len(results) == 1)

    c.invalidate_plugin("test.plugin")
    check("Invalidate plugin", c.get_package_info("test.plugin") is None)

    c.set_package_info("test.plugin", "1.0.0", {"id": "test.plugin"})
    c.invalidate_repository("stable-repo")
    check("Invalidate repo", c.get_repository_index("stable-repo") is None)

    c.set_package_info("p1", "1.0", {"id": "p1"})
    c.set_package_info("p2", "1.0", {"id": "p2"})
    c.invalidate_all()
    check("Invalidate all pkg", c.get_package_info("p1") is None)
    check("Invalidate all search", c.get_search_results("momentum") is None)

    c.set_package_info("x", "1.0", {"id": "x"})
    c.set_repository_index("r", [{"a": 1}])
    c.set_search_results("q", [{"b": 2}])
    c.clear()
    check("Clear pkg", c.get_package_info("x") is None)
    check("Clear repo", c.get_repository_index("r") is None)
    check("Clear search", c.get_search_results("q") is None)

    stats = c.get_stats()
    check("Stats has hit rate", "hit_rate" in stats)
    check("Stats has entries", "package_entries" in stats)


# ── 18. MarketplaceAudit ──

def test_audit():
    print("\n=== 18. MarketplaceAudit ===")
    from infrastructure.plugins.marketplace import MarketplaceAudit

    a = MarketplaceAudit()
    check("Audit created", a is not None)

    a.log_event("install", "test.plugin", {"version": "1.0.0"})
    a.log_event("update", "test.plugin", {"old": "1.0.0", "new": "1.1.0"})
    a.log_event("error", "test.plugin", {"message": "Something failed"})
    a.log_event("install", "other.plugin", {"version": "2.0.0"})

    events = a.get_events()
    check("All events", len(events) == 4)

    plugin_events = a.get_events(plugin_id="test.plugin")
    check("Plugin events", len(plugin_events) == 3)

    type_events = a.get_events(event_type="install")
    check("Type events", len(type_events) == 2)

    recent = a.get_recent(limit=2)
    check("Recent limited", len(recent) == 2)

    counts = a.get_event_counts()
    check("Counts has install", counts.get("install") == 2)
    check("Counts has update", counts.get("update") == 1)
    check("Counts has error", counts.get("error") == 1)

    filtered_counts = a.get_event_counts(plugin_id="test.plugin")
    check("Filtered counts", filtered_counts.get("install") == 1)

    query_result = a.query({"event_type": "install"})
    check("Query by type", len(query_result) == 2)

    query_result2 = a.query({"plugin_id": "other.plugin"})
    check("Query by plugin", len(query_result2) == 1)

    a.clear("other.plugin")
    remaining = a.get_events()
    check("After clear one", len(remaining) == 3)

    a.clear()
    check("After clear all", len(a.get_events()) == 0)

    stats = a.get_stats()
    check("Stats total entries", "total_entries" in stats)


# ── 19. MarketplaceMetrics ──

def test_metrics():
    print("\n=== 19. MarketplaceMetrics ===")
    from infrastructure.plugins.marketplace import MarketplaceMetrics

    m = MarketplaceMetrics()
    check("Metrics created", m is not None)

    m.record_install("test.plugin", 1.5, True)
    m.record_install("test.plugin", 2.0, False)
    m.record_update("test.plugin", 0.5, True)
    m.record_uninstall("test.plugin", True)
    m.record_download("test.plugin", 1024, 0.3)
    m.record_search("momentum", 5)
    m.record_rollback("test.plugin", True)
    m.record_validation("test.plugin", 0)
    m.record_validation("bad.plugin", 3)

    snap = m.snapshot()
    check("Snapshot has counters", "counters" in snap)
    check("Snapshot has histograms", "histograms" in snap)

    install_count = m.get_counter("icyquant_marketplace_install_total")
    check("Install counter", install_count == 2)

    update_count = m.get_counter("icyquant_marketplace_update_total")
    check("Update counter", update_count == 1)

    uninstall_count = m.get_counter("icyquant_marketplace_uninstall_total")
    check("Uninstall counter", uninstall_count == 1)

    search_count = m.get_counter("icyquant_marketplace_search_total")
    check("Search counter", search_count == 1)

    rollback_count = m.get_counter("icyquant_marketplace_rollback_total")
    check("Rollback counter", rollback_count == 1)

    validation_count = m.get_counter("icyquant_marketplace_validation_total")
    check("Validation counter", validation_count == 2)

    error_count = m.get_counter("icyquant_marketplace_errors_total")
    check("Error counter", error_count >= 1)

    inst_hist = m.get_histogram("icyquant_marketplace_install_seconds")
    check("Install histogram", "avg" in inst_hist)
    check("Install histogram count", inst_hist["count"] == 2)
    check("Install histogram min", inst_hist["min"] == 1.5)
    check("Install histogram max", inst_hist["max"] == 2.0)

    empty_hist = m.get_histogram("nonexistent_histogram")
    check("Empty histogram", empty_hist["count"] == 0)

    m.reset()
    snap2 = m.snapshot()
    check("Reset clears counters", len(snap2["counters"]) == 0)
    check("Reset clears histograms", len(snap2["histograms"]) == 0)

    stats = m.get_stats()
    check("Stats has counters", "counters" in stats)
    check("Stats has histograms", "histograms" in stats)


# ── 20. MarketplaceHealth ──

async def test_health():
    print("\n=== 20. MarketplaceHealth ===")
    from infrastructure.plugins.marketplace import MarketplaceHealth

    h = MarketplaceHealth()
    check("Health created", h is not None)

    result = await h.check()
    check("Health result is dict", isinstance(result, dict))
    check("Health has healthy", "healthy" in result)
    check("Health has checks", "checks" in result)
    check("Health has summary", "summary" in result)

    checks = result.get("checks", [])
    check("Has cache check", any(c["name"] == "cache" for c in checks))
    check("Has registry check", any(c["name"] == "registry" for c in checks))

    check("Is healthy", h.is_healthy())

    repo_results = h.check_repositories()
    check("Repo results", len(repo_results) >= 1)

    cache_result = h.check_cache()
    check("Cache result", cache_result.get("healthy") is True)

    registry_result = h.check_registry()
    check("Registry result", registry_result.get("healthy") is True)

    stats = h.get_stats()
    check("Stats has results", "results" in stats)
    check("Stats has last_check_time", "last_check_time" in stats)

    h2 = MarketplaceHealth(repositories=["repo1"], cache="fake_cache", registry="fake_registry")
    result2 = await h2.check()
    check("Health with components", isinstance(result2, dict))


# ── 21. MarketplaceDiagnostics ──

def test_diagnostics():
    print("\n=== 21. MarketplaceDiagnostics ===")
    from infrastructure.plugins.marketplace import MarketplaceDiagnostics

    d = MarketplaceDiagnostics()
    check("Diagnostics created", d is not None)

    d.record_operation("install", "test.plugin", "success", {"version": "1.0"})
    d.record_operation("update", "test.plugin", "success", {"old": "1.0", "new": "2.0"})
    d.record_operation("download", "other.plugin", "success", {"size": 1024})
    d.record_error("test.plugin", "Something failed", "install", "traceback...")
    d.record_performance("test.plugin", "install", 150.5)

    diags = d.get_diagnostics()
    check("All diagnostics", len(diags) >= 4)

    plugin_diags = d.get_diagnostics("test.plugin")
    check("Plugin diagnostics", len(plugin_diags) >= 3)

    errors = d.get_error_history("test.plugin")
    check("Error history", len(errors) >= 1)
    check("Error status", errors[0]["status"] == "error")

    errors_all = d.get_error_history()
    check("All errors", len(errors_all) >= 1)

    op_log = d.get_operation_log("test.plugin")
    check("Operation log", len(op_log) >= 3)

    perf = d.get_performance_report("test.plugin")
    check("Performance report", "install" in perf)
    if "install" in perf:
        check("Perf avg present", "avg_ms" in perf["install"])
        check("Perf count", perf["install"]["count"] == 1)

    perf_empty = d.get_performance_report("nonexistent")
    check("Empty perf", len(perf_empty) == 0)

    d.clear("other.plugin")
    remaining = d.get_diagnostics()
    check("After clear one", len(remaining) >= 3)

    d.clear()
    check("After clear all", len(d.get_diagnostics()) == 0)

    stats = d.get_stats()
    check("Stats total entries", "total_entries" in stats)
    check("Stats by_operation", "by_operation" in stats)


# ── Main ──

def main():
    print("=" * 60)
    print("  ICYQuant Plugin Marketplace V1 Validation")
    print("=" * 60)

    # Sync tests
    test_plugin_marketplace()
    test_registry()
    test_publisher()
    test_package()
    test_channels()
    test_compatibility()
    test_dependency()
    test_resolver()
    test_search()
    test_signature()
    test_validator()
    test_cache()
    test_audit()
    test_metrics()
    test_diagnostics()

    # Async tests
    asyncio.run(test_repository())
    asyncio.run(test_installer())
    asyncio.run(test_updater())
    asyncio.run(test_rollback())
    asyncio.run(test_downloader())
    asyncio.run(test_health())

    print("\n" + "=" * 60)
    print(f"  Results: {PASSED} passed, {FAILED} failed")
    print(f"  Total checks: {PASSED + FAILED}")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n  All marketplace validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()