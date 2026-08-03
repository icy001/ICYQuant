"""
Monitoring exceptions.

Defines exception hierarchy for the
monitoring infrastructure, enabling
precise error handling across collectors,
exporters, and the registry.
"""

from __future__ import annotations


class MonitoringError(Exception):
    """
    Base monitoring exception.

    All monitoring-specific exceptions
    inherit from this class.
    """


class CollectorError(MonitoringError):
    """
    Collector error.

    Raised when a metrics collector fails
    to collect data from an infrastructure
    component.
    """


class ExporterError(MonitoringError):
    """
    Exporter error.

    Raised when a metrics exporter fails
    to push data to a monitoring backend.
    """


class RegistryError(MonitoringError):
    """
    Registry error.

    Raised when the metrics registry
    encounters an issue with registration
    or collection.
    """


class HealthCheckError(MonitoringError):
    """
    Health check error.

    Raised when a health check fails
    to execute or returns invalid data.
    """
