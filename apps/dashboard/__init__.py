"""
ICYQuant Trading Dashboard.

The Dashboard is the human interaction / operational control surface
for ICYQuant. It is strictly API-only: every piece of data is served
by the Backend API gateway; the Dashboard never touches the database,
Redis, the event bus or any internal engine directly.

- apps/dashboard/auth.py    authentication + RBAC (reuses official security platform)
- apps/dashboard/runtime.py live read-only observation of a running pipeline
- apps/dashboard/api.py     FastAPI router exposed through the API gateway
- apps/dashboard/static/    zero-dependency browser SPA
"""

from __future__ import annotations

from apps.dashboard.api import router as dashboard_router

__all__ = ["dashboard_router"]
