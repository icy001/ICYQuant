"""
Trace exporters package.

Provides exporters for various OpenTelemetry-compatible
backends:

- ConsoleExporter: stdout (development)
- OTLPgRPCExporter: OTLP via gRPC
- OTLPHTTPExporter: OTLP via HTTP
- JaegerExporter: Jaeger
- TempoExporter: Grafana Tempo
- ZipkinExporter: Zipkin
- ExportManager: Multi-exporter coordination
- ExporterFactory: Factory for creating exporters
"""

from .base import TraceExporter
from .console import ConsoleExporter
from .factory import ExporterFactory
from .jaeger import JaegerExporter
from .manager import ExportManager
from .otlp_grpc import OTLPgRPCExporter
from .otlp_http import OTLPHTTPExporter
from .tempo import TempoExporter
from .zipkin import ZipkinExporter

__all__ = [
    "TraceExporter",
    "ConsoleExporter",
    "OTLPgRPCExporter",
    "OTLPHTTPExporter",
    "JaegerExporter",
    "TempoExporter",
    "ZipkinExporter",
    "ExportManager",
    "ExporterFactory",
]
