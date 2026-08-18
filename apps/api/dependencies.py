"""API dependency injection."""
from __future__ import annotations
from fastapi import Request

from core.bootstrap import BootstrapManager
from core.settings import Settings, get_settings

def get_bootstrap(request: Request) -> BootstrapManager:
    return request.app.state.bootstrap

def get_config() -> Settings:
    return get_settings()

def get_container(request: Request):
    bootstrap = get_bootstrap(request)
    return bootstrap.context.container