"""
Observability configuration registry.
"""

from __future__ import annotations

from .settings import (
    ObservabilitySettings,
    load_settings,
)


class ObservabilityConfig:
    def __init__(
        self,
        settings: ObservabilitySettings | None = None,
    ):
        self.settings = (
            settings
            or
            load_settings()
        )

    @property
    def service_name(self):
        return (
            self.settings.service_name
        )

    @property
    def tracing_enabled(self):
        return (
            self.settings.tracing_enabled
        )

    @property
    def metrics_enabled(self):
        return (
            self.settings.metrics_enabled
        )