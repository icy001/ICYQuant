"""
Exporter factory.

Creates exporter instances by type,
providing a unified interface for
configuring and instantiating exporters.

Supported types:
- otlp_grpc: OTLP gRPC exporter
- otlp_http: OTLP HTTP exporter
- jaeger: Jaeger exporter
- tempo: Grafana Tempo exporter
- zipkin: Zipkin exporter
- console: Console (stdout) exporter
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import TraceExporter
from .console import ConsoleExporter
from .jaeger import JaegerExporter
from .otlp_grpc import OTLPgRPCExporter
from .otlp_http import OTLPHTTPExporter
from .tempo import TempoExporter
from .zipkin import ZipkinExporter


class ExporterFactory:
    """
    Trace exporter factory.

    Creates exporter instances based on
    configuration, supporting all major
    OpenTelemetry-compatible backends.

    Usage:
        factory = ExporterFactory()
        exporter = factory.create("console")
        exporter = factory.create("otlp_grpc", endpoint="localhost:4317")
    """

    _registry: Dict[str, type] = {
        "console": ConsoleExporter,
        "otlp_grpc": OTLPgRPCExporter,
        "otlp_http": OTLPHTTPExporter,
        "jaeger": JaegerExporter,
        "tempo": TempoExporter,
        "zipkin": ZipkinExporter,
    }

    @classmethod
    def create(
        cls,
        exporter_type: str,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> TraceExporter:
        """
        Create an exporter by type.

        Args:
            exporter_type: Exporter type name.
            endpoint: Optional endpoint URL.
            **kwargs: Additional exporter configuration.

        Returns:
            TraceExporter instance.

        Raises:
            ValueError: If exporter type is unknown.
        """

        cls_type = cls._registry.get(exporter_type)
        if cls_type is None:
            raise ValueError(
                f"Unknown exporter type: {exporter_type}. "
                f"Supported: {', '.join(cls._registry.keys())}"
            )
        return cls_type(endpoint=endpoint, **kwargs)

    @classmethod
    def create_multiple(
        cls,
        configs: list,
    ) -> list:
        """
        Create multiple exporters from configs.

        Args:
            configs: List of dicts with 'type' and 'endpoint' keys.

        Returns:
            List of TraceExporter instances.
        """

        exporters = []
        for cfg in configs:
            etype = cfg.get("type", "console")
            endpoint = cfg.get("endpoint")
            kwargs = {k: v for k, v in cfg.items() if k not in ("type", "endpoint")}
            exporter = cls.create(etype, endpoint=endpoint, **kwargs)
            exporters.append(exporter)
        return exporters

    @classmethod
    def supported_types(cls) -> list:
        """Get list of supported exporter types."""
        return list(cls._registry.keys())

    @classmethod
    def register(
        cls,
        name: str,
        exporter_class: type,
    ) -> None:
        """Register a custom exporter type."""
        cls._registry[name] = exporter_class
