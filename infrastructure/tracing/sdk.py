"""
Tracing SDK.

High-level wrapper around OpenTelemetry's
SDK, providing a simple initialization
and configuration interface for the ICYQuant
platform.

Usage:
    sdk = TracingSDK(config=TracingConfig())
    sdk.initialize()
    tracer = sdk.get_tracer("icyquant")
"""

from __future__ import annotations

from typing import Any, List, Optional

from .config import TracingConfig
from .processor import ProcessorFactory
from .provider import ICYTracerProvider

try:
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
    from opentelemetry.baggage.propagation import (
        W3CBaggagePropagator,
    )
except ImportError:
    TraceContextTextMapPropagator = None
    W3CBaggagePropagator = None


class TracingSDK:
    """
    ICYQuant Tracing SDK.

    Provides a unified interface for initializing
    OpenTelemetry tracing with ICYQuant-specific
    defaults and configuration.

    Features:
    - One-line initialization
    - Automatic resource configuration
    - Span processor setup
    - W3C Trace Context propagation
    - Baggage support

    Usage:
        sdk = TracingSDK(config=TracingConfig())
        sdk.initialize()
        tracer = sdk.get_tracer("icyquant")
    """

    def __init__(
        self,
        config: Optional[TracingConfig] = None,
        exporters: Optional[List[Any]] = None,
    ) -> None:
        """
        Initialize SDK.

        Args:
            config: Tracing configuration.
            exporters: List of span exporters.
        """

        self._config = config or TracingConfig()
        self._exporters = exporters or []
        self._provider: Optional[ICYTracerProvider] = None
        self._tracer_provider: Any = None
        self._propagator: Any = None
        self._baggage_propagator: Any = None
        self._initialized: bool = False

    @property
    def is_initialized(
        self,
    ) -> bool:
        """Check if SDK is initialized."""
        return self._initialized

    @property
    def provider(
        self,
    ) -> Optional[ICYTracerProvider]:
        """Get ICYTracerProvider."""
        return self._provider

    def initialize(
        self,
    ) -> Any:
        """
        Initialize the tracing SDK.

        Creates the provider, sets up processors,
        and initializes propagators.

        Returns:
            TracerProvider instance.
        """

        if self._initialized:
            return self._tracer_provider

        # Create processors for exporters
        processors = []
        for exporter in self._exporters:
            proc = ProcessorFactory.create(exporter, mode="batch")
            if proc is not None:
                processors.append(proc)

        # Build provider
        self._provider = ICYTracerProvider(
            config=self._config,
            processors=processors,
        )
        self._tracer_provider = self._provider.build()

        # Initialize propagators
        if TraceContextTextMapPropagator is not None:
            self._propagator = TraceContextTextMapPropagator()

        if W3CBaggagePropagator is not None:
            self._baggage_propagator = W3CBaggagePropagator()

        self._initialized = True
        return self._tracer_provider

    def get_tracer(
        self,
        name: Optional[str] = None,
    ) -> Any:
        """
        Get a tracer.

        Args:
            name: Tracer name.

        Returns:
            Tracer instance.
        """

        if self._provider is None:
            return None
        return self._provider.get_tracer(name=name)

    @property
    def propagator(
        self,
    ) -> Any:
        """Get W3C Trace Context propagator."""
        return self._propagator

    @property
    def baggage_propagator(
        self,
    ) -> Any:
        """Get W3C Baggage propagator."""
        return self._baggage_propagator

    def shutdown(
        self,
    ) -> None:
        """Shutdown the SDK."""

        if self._provider is not None:
            self._provider.shutdown()
        self._initialized = False
