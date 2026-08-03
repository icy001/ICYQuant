"""
Span processor factory.

Creates and manages span processors for
the OpenTelemetry tracing pipeline.

Supported processors:
- SimpleSpanProcessor: Processes spans one at a time
- BatchSpanProcessor: Batches spans for efficiency
- CompositeProcessor: Chains multiple processors
"""

from __future__ import annotations

from typing import Any, List, Optional

try:
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SimpleSpanProcessor,
    )
except ImportError:
    BatchSpanProcessor = None
    SimpleSpanProcessor = None


class ProcessorFactory:
    """
    Span processor factory.

    Creates span processor instances for
    different processing strategies.

    Usage:
        factory = ProcessorFactory()
        batch_proc = factory.create_batch(exporter)
        simple_proc = factory.create_simple(exporter)
    """

    @staticmethod
    def create_simple(
        exporter: Any,
    ) -> Any:
        """
        Create a SimpleSpanProcessor.

        Processes spans immediately as they
        are finished. Best for development
        and low-volume scenarios.

        Args:
            exporter: Span exporter.

        Returns:
            SimpleSpanProcessor instance.
        """

        if SimpleSpanProcessor is None:
            return None
        return SimpleSpanProcessor(exporter)

    @staticmethod
    def create_batch(
        exporter: Any,
        max_queue_size: int = 2048,
        max_export_batch_size: int = 512,
        schedule_delay_millis: int = 5000,
    ) -> Any:
        """
        Create a BatchSpanProcessor.

        Buffers spans and exports them in
        batches, reducing overhead. Best for
        production use.

        Args:
            exporter: Span exporter.
            max_queue_size: Max queue size.
            max_export_batch_size: Max batch size.
            schedule_delay_millis: Flush interval.

        Returns:
            BatchSpanProcessor instance.
        """

        if BatchSpanProcessor is None:
            return None
        return BatchSpanProcessor(
            exporter,
            max_queue_size=max_queue_size,
            max_export_batch_size=max_export_batch_size,
            schedule_delay_millis=schedule_delay_millis,
        )

    @staticmethod
    def create_composite(
        exporters: List[Any],
        use_batch: bool = True,
    ) -> List[Any]:
        """
        Create processors for multiple exporters.

        Args:
            exporters: List of span exporters.
            use_batch: Whether to use batch processing.

        Returns:
            List of span processors.
        """

        processors = []
        for exporter in exporters:
            if use_batch:
                proc = ProcessorFactory.create_batch(exporter)
            else:
                proc = ProcessorFactory.create_simple(exporter)
            if proc is not None:
                processors.append(proc)
        return processors

    @staticmethod
    def create(
        exporter: Any,
        mode: str = "batch",
    ) -> Any:
        """
        Create a span processor by mode.

        Args:
            exporter: Span exporter.
            mode: "simple" or "batch".

        Returns:
            Span processor instance.
        """

        if mode == "simple":
            return ProcessorFactory.create_simple(exporter)
        return ProcessorFactory.create_batch(exporter)
