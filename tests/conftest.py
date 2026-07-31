"""Shared test fixtures for ICYQuant."""
from __future__ import annotations
import os
import sys
import pytest

@pytest.fixture(autouse=True)
def env_test_mode():
    """Ensure tests run in test mode."""
    os.environ["APP_ENV"] = "test"
    yield
    for key in list(os.environ.keys()):
        if key.startswith("ICYQUANT_"):
            del os.environ[key]

@pytest.fixture
def sample_config():
    return {
        "APP_NAME": "ICYQuant Test",
        "APP_VERSION": "0.4.0-alpha2",
        "APP_ENV": "test",
        "APP_HOST": "127.0.0.1",
        "APP_PORT": 8000,
    }
