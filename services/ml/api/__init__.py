"""ML Platform API.

REST API for experiment tracking, model registry, artifact management,
and platform status.
"""

from __future__ import annotations

from services.ml.api.ml_api import router

__all__ = ["router"]
