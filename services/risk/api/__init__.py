from .risk_api import get_risk_snapshot, run_stress_test, get_risk_report_api


# NOTE: APIResponse and RiskAPI are defined in services/risk/api.py
# (the module file), but the api/ directory package shadows it.
# To avoid the package-vs-module name conflict, forward-declarations
# are provided here so that risk/__init__.py can import them.
# The actual implementations live in services/risk/api.py and will
# be decorated / replaced at runtime by the service bootstrap.

from typing import Any, Optional


class APIResponse:
    """Stub — actual impl in services.risk.api module."""
    def __init__(self, success: bool = True, data: Optional[Any] = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "data": self.data, "error": self.error}


class RiskAPI:
    """Stub — actual impl in services.risk.api module."""
    def __init__(self, risk_service=None, risk_bootstrap=None):
        self._risk_service = risk_service
        self._risk_bootstrap = risk_bootstrap


__all__ = [
    "get_risk_snapshot",
    "run_stress_test",
    "get_risk_report_api",
    "APIResponse",
    "RiskAPI",
]
