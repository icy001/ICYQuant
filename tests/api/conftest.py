"""Shared fixtures for the API-level test suites.

Both the behaviour gate (``test_market_data_api.py``) and the contract
gate (``test_market_data_contract.py``) drive the real gateway via
``TestClient(apps.api.main.app)`` exactly like a browser or an external
client would, and both need the same three things: a seeded auth store,
a token, and a pipeline warm enough to serve real quotes.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.dashboard.auth import auth as dashboard_auth
from services.market_data.market_data_service import market_data_service

# Seed Dashboard users/roles up-front so the gateway works even when
# the TestClient lifespan is not triggered.
dashboard_auth.seed()

client = TestClient(app)


def login(username: str, password: str) -> str:
    res = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def gateway() -> TestClient:
    return client


@pytest.fixture(scope="session")
def reader() -> dict:
    """Read-only client headers (every read endpoint needs a token)."""
    return headers(login("readonly", "readonly123"))


@pytest.fixture(scope="session")
def warm(reader: dict) -> dict:
    """Boot ingestion and wait until real quotes are flowing.

    The pipeline is the same one Commits 003–009 built: a lazy-started
    quote feed backed by the real adapter, not a test double.
    """
    market_data_service.ensure_feed()
    # The mock adapter picks one symbol per tick, so "some quote arrived"
    # is not the same as "the universe is warm" — wait for full coverage
    # so a symbol-scoped test can never race an empty book.
    deadline = time.time() + 30.0
    while time.time() < deadline:
        body = client.get("/api/market-data/health", headers=reader).json()
        counts = body["symbols"]
        if counts["total"] and not counts["offline"]:
            return reader
        time.sleep(0.5)
    pytest.fail("no real quote ever reached the Market Data API")
