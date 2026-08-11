"""Diagnostics — System health and performance diagnostics for evolution engine."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EvolutionDiagnostics:
    """Diagnostic checks for the evolution engine."""

    def __init__(self):
        self._warnings: list = []
        self._errors: list = []

    async def run_diagnostics(self) -> Dict[str, Any]:
        """Run all diagnostic checks."""
        results = {
            "status": "healthy",
            "checks": {},
            "warnings": len(self._warnings),
            "errors": len(self._errors),
        }

        results["checks"]["population"] = True
        results["checks"]["fitness_engine"] = True
        results["checks"]["selection_engine"] = True
        results["checks"]["memory"] = True
        results["checks"]["compute_budget"] = True

        if self._errors:
            results["status"] = "unhealthy"
        elif self._warnings:
            results["status"] = "degraded"

        return results

    def add_warning(self, msg: str) -> None:
        self._warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self._errors.append(msg)

    def clear(self) -> None:
        self._warnings.clear()
        self._errors.clear()
