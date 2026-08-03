"""
OpenTelemetry Tracer Provider.

Provides a unified TracerProvider for the
ICYQuant platform, wrapping OpenTelemetry's
SDK TracerProvider with ICYQuant-specific
configuration and resource management.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .config import TracingConfig
from .resource import build_resource

try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor,
    )
except ImportError:
    TracerProvider = None
    SimpleSpanProcessor = None


class ICYTracerProvider:
    """
    ICYQuant Tracer Provider.

    Wraps OpenTelemetry's TracerProvider with
    ICYQuant-specific configuration, resource
    management, and span processor setup.

    Usage:
        provider = ICYTracerProvider(config=TracingConfig())
        tracer_provider = provider.build()
    """

    def __init__(
        self,
        config: Optional[TracingConfig] = None,
        processors: Optional[List[Any]] = None,
    ) -> None:
        """
        Initialize provider.

        Args:
            config: Tracing configuration.
            processors: List of span processors.
        """

        self._config = config or TracingConfig()
        self._processors = processors or []
        self._provider: Any = None

    @property
    def provider(
        self,
    ) -> Any:
        """Get the built TracerProvider."""
        return self._provider

    def build(
        self,
    ) -> Any:
        """
        Build the TracerProvider.

        Creates a resource from config and
        instantiates the TracerProvider.

        Returns:
            TracerProvider instance.
        """

        if TracerProvider is None:
            return None

        resource = build_resource(
            service_name=self._config.service_name,
            environment=self._config.environment,
        )

        self._provider = TracerProvider(resource=resource)

        for processor in self._processors:
            self._provider.add_span_processor(processor)

        return self._provider

    def add_processor(
        self,
        processor: Any,
    ) -> None:
        """
        Add a span processor.

        Args:
            processor: Span processor to add.
        """

        self._processors.append(processor)
        if self._provider is not None:
            self._provider.add_span_processor(processor)

    def get_tracer(
        self,
        name: Optional[str] = None,
    ) -> Any:
        """
        Get a tracer from the provider.

        Args:
            name: Tracer name (defaults to service name).

        Returns:
            Tracer instance.
        """

        if self._provider is None:
            return None

        return self._provider.get_tracer(
            name or self._config.service_name,
            self._config.service_name,
        )

    def shutdown(
        self,
    ) -> None:
        """Shutdown the provider."""

        if self._provider is not None and hasattr(self._provider, "shutdown"):
            self._provider.shutdown()
