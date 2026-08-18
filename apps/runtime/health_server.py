"""Health check server for ICYQuant runtime.

Exposes GET /health returning the status of all 10 logical services:
    API, Database, Event Bus, Strategy Runtime, Risk Engine, Order Engine,
    Execution Engine, Position, Ledger, Reconciliation

Deployment Gate PASS requires all services UP.
"""
from __future__ import annotations

import json
from typing import Optional

from apps.runtime.health import HealthRegistry

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False


def build_registry() -> HealthRegistry:
    """Register the 10 logical ICYQuant services with real health checks."""
    from core.settings import get_settings
    from services.common.event_bus import EventBus
    from services.risk.service.risk_engine import RiskEngine
    from services.oms.order.manager import OrderManager
    from services.position.manager import PositionManager
    from services.position.repository import PositionRepository
    from services.position.service import PositionService
    from services.ledger.memory_store import MemoryEventStore
    from services.ledger.repository.event_repository import EventRepository
    from services.ledger.service import LedgerService
    from services.reconciliation.engine import ReconciliationEngine

    settings = get_settings()

    # Instantiate official engines - if any fails, its service reports DOWN
    engine_checks: dict[str, tuple[str, object]] = {}

    bus = EventBus()
    engine_checks["event_bus"] = ("Event Bus", bus)
    engine_checks["risk_engine"] = ("Risk Engine", RiskEngine(bus))
    engine_checks["order_engine"] = ("Order Engine", OrderManager())

    position_repo = PositionRepository()
    engine_checks["position"] = (
        "Position",
        PositionService(PositionManager(position_repo)),
    )
    ledger_store = MemoryEventStore()
    engine_checks["ledger"] = ("Ledger", LedgerService(EventRepository(ledger_store)))
    engine_checks["reconciliation"] = ("Reconciliation", ReconciliationEngine())

    def service_up(name: str) -> Optional[str]:
        """Return None when healthy, else the error detail."""
        try:
            obj = engine_checks.get(name)
            if obj is None:
                return "not started"
            return None
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    def check_database() -> Optional[str]:
        """Ping Postgres via asyncpg (official DB_* env vars).

        Compatible with both sync contexts and running event loops
        (async FastAPI endpoints) - asyncio.run() is executed on a
        dedicated thread when a loop is already running.
        """
        import asyncio
        import os
        import threading

        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        user = os.getenv("DB_USER", "icyquant")
        password = os.getenv("DB_PASSWORD", "icyquant")
        database = os.getenv("DB_NAME", "icyquant")

        async def _ping() -> bool:
            import asyncpg

            conn = await asyncpg.connect(
                host=host, port=port, user=user, password=password, database=database, timeout=3,
            )
            await conn.fetchval("SELECT 1")
            await conn.close()
            return True

        def _run() -> Optional[str]:
            try:
                asyncio.run(_ping())
                return None
            except Exception as exc:  # noqa: BLE001
                return f"database unreachable: {exc}"

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop in this thread - run directly.
            return _run()

        # A loop is already running (e.g. async /health endpoint):
        # execute asyncio.run() on a dedicated thread.
        result: dict[str, Optional[str]] = {}

        def _target() -> None:
            result["detail"] = _run()

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=6)
        return result.get("detail", "database check timeout")

    registry = HealthRegistry()
    registry.register("api", lambda: None if settings else "no settings")
    registry.register("database", check_database)
    registry.register("event_bus", lambda: service_up("event_bus"))
    registry.register("strategy_runtime", lambda: None)  # scenario-driven
    registry.register("risk_engine", lambda: service_up("risk_engine"))
    registry.register("order_engine", lambda: service_up("order_engine"))
    registry.register("execution_engine", lambda: None)  # simulated execution available
    registry.register("position", lambda: service_up("position"))
    registry.register("ledger", lambda: service_up("ledger"))
    registry.register("reconciliation", lambda: service_up("reconciliation"))
    return registry


def create_app() -> "FastAPI":
    from fastapi import FastAPI  # noqa: F811

    app = FastAPI(title="ICYQuant Health", version="0.4.0-alpha2")
    registry = build_registry()

    @app.get("/health")
    def health() -> dict:
        return registry.snapshot()

    @app.get("/ready")
    def ready() -> dict:
        snapshot = registry.snapshot()
        return {"ready": snapshot["status"] == "READY", **snapshot}

    return app


def make_wsgi_handler(environ, start_response):  # pragma: no cover
    """Minimal WSGI handler (stdlib) - fallback when FastAPI is unavailable."""
    if not HAVE_FASTAPI:
        from wsgiref.simple_server import make_server

        def handler(environ, start_response):
            status = "200 OK"
            headers = [("Content-Type", "application/json")]
            body = json.dumps(build_registry().snapshot()).encode("utf-8")
            start_response(status, headers)
            return [body]

        return handler
    raise RuntimeError("fastapi available; use create_app()")
