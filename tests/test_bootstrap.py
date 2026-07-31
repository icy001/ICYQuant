"""Tests for platform bootstrap and core foundation."""
from __future__ import annotations
import os
import pytest

os.environ.setdefault("APP_ENV", "test")

from core.bootstrap import Bootstrap
from core.container import Container
from core.health import HealthChecker, HealthComponent, HealthStatus
from core.lifecycle import LifecycleManager, LifecycleState, LifecyclePhase
from core.registry import ModuleRegistry, ModuleInfo
from core.settings import Settings, get_settings
from shared.constants import APP_NAME, APP_VERSION, ModuleType, ServiceStatus
from shared.exceptions import (
    ICYQuantError,
    ConfigurationError,
    ValidationError,
    NotFoundError,
)
from shared.result import Result, PaginatedResult
from shared.types import Timestamp, Pagination, Metadata, generate_id
from shared.utils import (
    generate_hash,
    deep_merge,
    retry,
    env_var,
    mask_sensitive,
    format_bytes,
)


class TestBootstrap:
    """Tests for Bootstrap orchestrator."""

    def test_create_bootstrap(self):
        bootstrap = Bootstrap()
        assert bootstrap is not None
        assert bootstrap.container is not None
        assert bootstrap.registry is not None
        assert bootstrap.lifecycle is not None
        assert bootstrap.health_checker is not None

    def test_initialize_succeeds(self):
        bootstrap = Bootstrap()
        result = bootstrap.initialize()
        assert result is True
        assert bootstrap.is_ready()

    def test_shutdown_succeeds(self):
        bootstrap = Bootstrap()
        bootstrap.initialize()
        bootstrap.shutdown()
        status = bootstrap.get_status()
        assert status["status"] == ServiceStatus.STOPPED.value

    def test_status_before_init(self):
        bootstrap = Bootstrap()
        status = bootstrap.get_status()
        assert status["phase"] == "created"
        assert status["status"] == ServiceStatus.CREATED.value

    def test_status_after_init(self):
        bootstrap = Bootstrap()
        bootstrap.initialize()
        status = bootstrap.get_status()
        assert status["phase"] == "ready"
        assert status["progress"] == 100
        assert len(status["steps"]) > 0

    def test_register_shutdown_hook(self):
        bootstrap = Bootstrap()
        called = []
        bootstrap.register_shutdown_hook(lambda: called.append("shutdown"))
        bootstrap.initialize()
        bootstrap.shutdown()
        assert "shutdown" in called


class TestSettings:
    """Tests for Settings management."""

    def test_default_settings(self):
        settings = Settings()
        assert settings.APP_NAME == "ICYQuant"
        assert settings.APP_PORT == 8000

    def test_custom_env(self):
        os.environ["APP_ENV"] = "production"
        settings = Settings()
        assert settings.APP_ENV == "production"
        assert settings.is_production is True
        assert settings.is_development is False

    def test_is_test(self):
        os.environ["APP_ENV"] = "test"
        settings = Settings()
        assert settings.is_test is True

    def test_get_settings_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestLifecycle:
    """Tests for LifecycleManager."""

    def test_register_module(self):
        lm = LifecycleManager()
        lm.register("test_module")
        assert lm.get_state("test_module") == LifecycleState.CREATED

    def test_initialize_module(self):
        lm = LifecycleManager()
        lm.register("test_module")
        result = lm.initialize("test_module")
        assert result is True
        assert lm.get_state("test_module") == LifecycleState.INITIALIZING

    def test_start_module(self):
        lm = LifecycleManager()
        lm.register("test_module")
        result = lm.start("test_module")
        assert result is True
        assert lm.get_state("test_module") == LifecycleState.RUNNING

    def test_stop_module(self):
        lm = LifecycleManager()
        lm.register("test_module")
        lm.start("test_module")
        result = lm.stop("test_module")
        assert result is True
        assert lm.get_state("test_module") == LifecycleState.STOPPED

    def test_invalid_transition(self):
        lm = LifecycleManager()
        lm.register("test_module")
        result = lm.transition("test_module", LifecycleState.RUNNING)
        assert result is False

    def test_lifecycle_history(self):
        lm = LifecycleManager()
        lm.register("test_module")
        lm.start("test_module")
        lm.stop("test_module")
        history = lm.get_history("test_module")
        assert len(history) > 0

    def test_on_phase_handler(self):
        lm = LifecycleManager()
        lm.register("test_module")
        called = []
        lm.on_phase("test_module", LifecyclePhase.START, lambda n, f, t: called.append(n))
        lm.start("test_module")
        assert "test_module" in called

    def test_get_status(self):
        lm = LifecycleManager()
        lm.register("mod1")
        lm.register("mod2")
        lm.start("mod1")
        status = lm.get_status()
        assert status["total_modules"] == 2
        assert status["active_modules"] == 1


class TestModuleRegistry:
    """Tests for ModuleRegistry."""

    def test_register_module(self):
        reg = ModuleRegistry()
        info = reg.register("test", ModuleType.MARKET, "1.0.0", "Test module")
        assert info.name == "test"
        assert info.module_type == ModuleType.MARKET
        assert "test" in reg

    def test_get_module(self):
        reg = ModuleRegistry()
        reg.register("test", ModuleType.MARKET)
        info = reg.get("test")
        assert info is not None
        assert info.name == "test"

    def test_list_by_type(self):
        reg = ModuleRegistry()
        reg.register("m1", ModuleType.MARKET)
        reg.register("m2", ModuleType.RISK)
        reg.register("m3", ModuleType.MARKET)
        market_modules = reg.list_modules(ModuleType.MARKET)
        assert len(market_modules) == 2

    def test_ordered_by_dependencies(self):
        reg = ModuleRegistry()
        reg.register("base", ModuleType.PLATFORM)
        reg.register("dependent", ModuleType.RISK, dependencies=["base"])
        ordered = reg.ordered_by_dependencies()
        names = [m.name for m in ordered]
        assert names.index("base") < names.index("dependent")

    def test_set_get_instance(self):
        reg = ModuleRegistry()
        reg.register("test", ModuleType.MARKET)
        obj = object()
        reg.set_instance("test", obj)
        assert reg.get_instance("test") is obj

    def test_get_status(self):
        reg = ModuleRegistry()
        reg.register("m1", ModuleType.MARKET)
        reg.register("m2", ModuleType.RISK)
        status = reg.get_status()
        assert status["total_modules"] == 2
        assert "market" in status["by_type"]


class TestContainer:
    """Tests for Container."""

    def test_register_singleton(self):
        c = Container()
        obj = object()
        c.register_singleton(object, obj)
        assert c.get(object) is obj

    def test_register_factory(self):
        c = Container()
        call_count = [0]

        def factory():
            call_count[0] += 1
            return call_count[0]

        c.register_factory(int, factory)
        v1 = c.get(int)
        v2 = c.get(int)
        assert v1 == v2 == 1
        assert call_count[0] == 1

    def test_unregistered_type_raises(self):
        c = Container()
        with pytest.raises(Exception):
            c.get(str)

    def test_named_registration(self):
        c = Container()
        c.register_instance("config", {"key": "value"})
        assert c.get_named("config") == {"key": "value"}

    def test_clear(self):
        c = Container()
        c.register_singleton(str, "test")
        c.clear()
        assert len(c.get_registered_types()) == 0


class TestHealthChecker:
    """Tests for HealthChecker."""

    def test_register_check(self):
        hc = HealthChecker()
        hc.register("test", lambda: HealthComponent(name="test", status=HealthStatus.HEALTHY))
        assert "test" in hc

    def test_check_all(self):
        hc = HealthChecker()
        hc.register("svc1", lambda: HealthComponent(name="svc1", status=HealthStatus.HEALTHY))
        hc.register("svc2", lambda: HealthComponent(name="svc2", status=HealthStatus.HEALTHY))
        results = hc.check_all()
        assert len(results) == 2

    def test_overall_status_healthy(self):
        hc = HealthChecker()
        hc.register("test", lambda: HealthComponent(name="test", status=HealthStatus.HEALTHY))
        assert hc.get_overall_status() == HealthStatus.HEALTHY

    def test_overall_status_unhealthy(self):
        hc = HealthChecker()
        hc.register("test", lambda: HealthComponent(name="test", status=HealthStatus.UNHEALTHY))
        hc.check_all()
        assert hc.get_overall_status() == HealthStatus.UNHEALTHY

    def test_is_ready(self):
        hc = HealthChecker()
        hc.register("test", lambda: HealthComponent(name="test", status=HealthStatus.HEALTHY))
        assert hc.is_ready() is True

    def test_exception_in_check(self):
        hc = HealthChecker()

        def bad_check():
            raise RuntimeError("fail")

        hc.register("bad", bad_check)
        result = hc.check("bad")
        assert result.status == HealthStatus.UNHEALTHY

    def test_get_status(self):
        hc = HealthChecker()
        hc.register("test", lambda: HealthComponent(name="test", status=HealthStatus.HEALTHY))
        status = hc.get_status()
        assert status["status"] == "healthy"
        assert status["healthy"] == 1


class TestExceptions:
    """Tests for exception hierarchy."""

    def test_base_exception(self):
        err = ICYQuantError("test error", error_code=1000)
        assert str(err) == "test error"
        assert err.error_code == 1000

    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        assert err.error_code == 1001

    def test_validation_error(self):
        err = ValidationError("invalid data")
        assert err.error_code == 2000

    def test_not_found_error(self):
        err = NotFoundError("missing")
        assert err.error_code == 3000

    def test_exception_hierarchy(self):
        assert issubclass(ConfigurationError, ICYQuantError)
        assert issubclass(ValidationError, ICYQuantError)


class TestResult:
    """Tests for Result type."""

    def test_ok_result(self):
        r = Result.ok(42)
        assert r.success is True
        assert r.data == 42
        assert bool(r) is True

    def test_fail_result(self):
        err = ICYQuantError("fail")
        r = Result.fail(err)
        assert r.success is False
        assert r.failed is True
        assert r.error_message == "fail"

    def test_unwrap_success(self):
        r = Result.ok(100)
        assert r.unwrap() == 100

    def test_unwrap_failure(self):
        r = Result.fail(ICYQuantError("error"))
        with pytest.raises(ICYQuantError):
            r.unwrap()

    def test_unwrap_or(self):
        r = Result.fail(ICYQuantError("error"))
        assert r.unwrap_or(42) == 42

    def test_map_success(self):
        r = Result.ok(5)
        r2 = r.map(lambda x: x * 2)
        assert r2.data == 10

    def test_warnings(self):
        r = Result.ok("data", warnings=["warning1", "warning2"])
        assert len(r.warnings) == 2

    def test_to_dict(self):
        r = Result.ok("test", meta="value")
        d = r.to_dict()
        assert d["success"] is True
        assert d["data"] == "test"

    def test_paginated_result(self):
        pr = PaginatedResult.create([1, 2, 3], 10, 1, 3)
        assert pr.total_pages == 4
        assert pr.has_next is True
        assert pr.has_prev is False

    def test_paginated_result_last_page(self):
        pr = PaginatedResult.create([], 10, 4, 3)
        assert pr.has_next is False
        assert pr.has_prev is True


class TestTypes:
    """Tests for shared types."""

    def test_generate_id(self):
        id1 = generate_id("test_")
        assert id1.startswith("test_")
        assert len(id1) > 5

    def test_timestamp_touch(self):
        ts = Timestamp()
        old = ts.updated_at
        ts.touch()
        assert ts.updated_at >= old

    def test_pagination_defaults(self):
        p = Pagination()
        assert p.page == 1
        assert p.page_size == 100

    def test_metadata(self):
        m = Metadata(tags={"env": "test"})
        assert "env" in m.tags


class TestUtils:
    """Tests for utility functions."""

    def test_generate_hash(self):
        h = generate_hash("hello")
        assert len(h) == 64
        assert h == generate_hash("hello")
        assert h != generate_hash("world")

    def test_deep_merge(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 10, "d": 3}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 10, "c": 2, "d": 3}}

    def test_retry(self):
        attempts = [0]

        @retry(max_attempts=3, delay=0.01)
        def flaky_func():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("fail")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert attempts[0] == 3

    def test_env_var(self):
        os.environ["TEST_VAR"] = "hello"
        assert env_var("TEST_VAR") == "hello"
        assert env_var("MISSING_VAR", "default") == "default"
        assert env_var("TEST_VAR", cast=int) is None

    def test_mask_sensitive(self):
        masked = mask_sensitive("sk-abcdefghijklmnopqrstuv", keep_start=3, keep_end=0)
        assert masked.startswith("sk-")
        assert "*" in masked
        assert mask_sensitive("ab") == "**"

    def test_format_bytes(self):
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1048576) == "1.00 MB"
        assert format_bytes(1073741824) == "1.00 GB"


class TestConstants:
    """Tests for constants."""

    def test_app_name(self):
        assert APP_NAME == "ICYQuant"

    def test_app_version(self):
        assert APP_VERSION == "0.4.0-alpha2"

    def test_module_type(self):
        assert ModuleType.MARKET.value == "market"
        assert ModuleType.RISK.value == "risk"

    def test_service_status(self):
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.STOPPED.value == "stopped"
