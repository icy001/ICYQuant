"""Tool SDK — developer-friendly API for registering tools in the ICYQuant platform.

Pipeline:
    Developer defines tool
        -> @tool decorator
        -> Auto-registration with ToolRegistry
        -> Auto-schema generation from type hints
        -> Ready for Discovery / Selection / Execution

The Tool SDK provides a unified development interface for building
tools that integrate with the AI Agent platform.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── ToolSDK ──

class ToolSDK:
    """Developer SDK for creating and registering tools.

    Provides decorators and helper functions for defining tools
    with automatic schema generation, validation, and registration.

    Supports:
        - @tool decorator for easy tool definition
        - Automatic input/output schema from type hints
        - Tool registration with the registry
        - Tool discovery and listing
        - Batch tool creation from modules

    Usage:
        sdk = ToolSDK(registry)

        @sdk.tool(
            name="backtest.run",
            description="Run a backtest",
            permission="research.execute",
            category="research",
        )
        async def run_backtest(strategy_id: str, start_date: str, end_date: str):
            ...

        # Or standalone:
        @tool(name="market.get_price", permission="market_data.read")
        async def get_price(symbol: str) -> dict:
            ...
    """

    def __init__(self, registry: Any = None) -> None:
        """Initialize the SDK.

        Args:
            registry: Optional ToolRegistry for auto-registration.
        """
        self._registry = registry
        self._created_tools: List[ToolDefinition] = []
        self._initialized: bool = False
        logger.info("ToolSDK created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the SDK."""
        self._initialized = True
        logger.info("ToolSDK initialized")

    async def shutdown(self) -> None:
        """Shutdown the SDK."""
        self._created_tools.clear()
        self._initialized = False
        logger.info("ToolSDK shutdown complete")

    # ── Tool Decorator ──

    def tool(
        self,
        name: str,
        description: str = "",
        permission: str = "default.read",
        category: str = "general",
        version: str = "1.0.0",
        risk_level: str = "low",
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        is_idempotent: bool = False,
        is_streaming: bool = False,
        tags: Optional[List[str]] = None,
        capability: str = "",
    ) -> Callable:
        """Decorator to register a function as a tool.

        Args:
            name: Unique tool name (e.g., "backtest.run").
            description: Human-readable description.
            permission: Required permission string.
            category: Tool category.
            version: Tool version.
            risk_level: Risk level (low/medium/high/critical).
            timeout_seconds: Execution timeout.
            max_retries: Maximum retry attempts.
            is_idempotent: Whether the tool is idempotent (cacheable).
            is_streaming: Whether the tool supports streaming.
            tags: Optional tags for discovery.
            capability: Capability string for discovery.

        Returns:
            A decorator function.
        """

        def decorator(func: Callable) -> Callable:
            # Generate input/output schemas from function signature
            inputs = self._infer_inputs(func)
            outputs = self._infer_outputs(func)

            definition = ToolDefinition(
                name=name,
                description=description or func.__doc__ or "",
                version=version,
                inputs=inputs,
                outputs=outputs,
                category=category,
                tags=tags or [],
                capability=capability or category,
                permission=permission,
                risk_level=risk_level,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                is_idempotent=is_idempotent,
                is_streaming=is_streaming,
                handler=func,
            )

            self._created_tools.append(definition)

            # Auto-register if registry is available
            if self._registry:
                try:
                    self._registry.register(definition)
                except ValueError as e:
                    logger.warning(f"Tool '{name}' already registered: {e}")

            logger.info(f"Tool created via SDK: {name}")
            return func

        return decorator

    # ── Schema Inference ──

    @staticmethod
    def _infer_inputs(func: Callable) -> List[ToolInput]:
        """Infer input schema from function signature.

        Args:
            func: The tool function.

        Returns:
            List of ToolInput definitions.
        """
        inputs: List[ToolInput] = []
        try:
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                # Skip 'self', 'cls', 'context'
                if param_name in ("self", "cls", "context"):
                    continue

                type_str = "string"
                if param.annotation != inspect.Parameter.empty:
                    type_str = ToolSDK._annotation_to_type(param.annotation)

                is_required = param.default == inspect.Parameter.empty
                default = None if is_required else param.default

                inputs.append(
                    ToolInput(
                        name=param_name,
                        type=type_str,
                        description=f"Parameter: {param_name}",
                        required=is_required,
                        default=default,
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to infer inputs from {func.__name__}: {e}")

        return inputs

    @staticmethod
    def _infer_outputs(func: Callable) -> List[ToolOutput]:
        """Infer output schema from function return annotation.

        Args:
            func: The tool function.

        Returns:
            List of ToolOutput definitions.
        """
        outputs: List[ToolOutput] = []
        try:
            sig = inspect.signature(func)
            if sig.return_annotation != inspect.Signature.empty:
                type_str = ToolSDK._annotation_to_type(sig.return_annotation)
                outputs.append(
                    ToolOutput(name="result", type=type_str, description="Execution result")
                )
        except Exception as e:
            logger.warning(f"Failed to infer outputs from {func.__name__}: {e}")

        if not outputs:
            outputs.append(
                ToolOutput(name="result", type="object", description="Execution result")
            )

        return outputs

    @staticmethod
    def _annotation_to_type(annotation: Any) -> str:
        """Convert a Python type annotation to a JSON schema type.

        Args:
            annotation: The type annotation.

        Returns:
            JSON schema type string.
        """
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }

        # Handle Optional[X]
        origin = getattr(annotation, "__origin__", None)
        if origin is not None:
            return "object"

        return type_map.get(annotation, "string")

    # ── Batch Registration ──

    def create_tool(
        self,
        name: str,
        func: Callable,
        description: str = "",
        permission: str = "default.read",
        category: str = "general",
        **kwargs: Any,
    ) -> ToolDefinition:
        """Create a tool definition programmatically.

        Args:
            name: Tool name.
            func: The handler function.
            description: Human-readable description.
            permission: Required permission.
            category: Tool category.
            **kwargs: Additional ToolDefinition fields.

        Returns:
            The created ToolDefinition.
        """
        definition = ToolDefinition(
            name=name,
            description=description or func.__doc__ or "",
            inputs=self._infer_inputs(func),
            outputs=self._infer_outputs(func),
            category=category,
            permission=permission,
            handler=func,
            **kwargs,
        )
        self._created_tools.append(definition)

        if self._registry:
            try:
                self._registry.register(definition)
            except ValueError as e:
                logger.warning(f"Tool '{name}' already registered: {e}")

        return definition

    def register_all(self, registry: Any) -> int:
        """Register all created tools with a registry.

        Args:
            registry: The ToolRegistry to register with.

        Returns:
            Number of tools registered.
        """
        count = 0
        for tool_def in self._created_tools:
            try:
                registry.register(tool_def)
                count += 1
            except ValueError as e:
                logger.warning(f"Tool registration skipped: {e}")
        logger.info(f"Registered {count} tools via SDK")
        return count

    # ── Listing ──

    def list_created(self) -> List[ToolDefinition]:
        """List all tools created via this SDK instance."""
        return list(self._created_tools)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get SDK status."""
        return {
            "created_tools": len(self._created_tools),
            "tool_names": [t.name for t in self._created_tools],
            "has_registry": self._registry is not None,
            "initialized": self._initialized,
        }


# ── Standalone tool decorator ──

@dataclass
class _ToolDecoratorState:
    """Holds state for the standalone @tool decorator."""

    created: List[ToolDefinition] = field(default_factory=list)


_standalone_state = _ToolDecoratorState()


def tool(
    name: str,
    description: str = "",
    permission: str = "default.read",
    category: str = "general",
    version: str = "1.0.0",
    risk_level: str = "low",
    timeout_seconds: float = 30.0,
    max_retries: int = 0,
    is_idempotent: bool = False,
    is_streaming: bool = False,
    tags: Optional[List[str]] = None,
    capability: str = "",
) -> Callable:
    """Standalone decorator to define a tool outside of SDK context.

    Usage:
        @tool(name="market.get_price", permission="market_data.read")
        async def get_price(symbol: str) -> dict:
            ...

    Args:
        name: Unique tool name.
        description: Human-readable description.
        permission: Required permission string.
        category: Tool category.
        version: Tool version.
        risk_level: Risk level.
        timeout_seconds: Execution timeout.
        max_retries: Maximum retry attempts.
        is_idempotent: Whether the tool is idempotent.
        is_streaming: Whether the tool supports streaming.
        tags: Optional tags.
        capability: Capability string.

    Returns:
        A decorator function.
    """

    def decorator(func: Callable) -> Callable:
        sdk = ToolSDK()
        inputs = sdk._infer_inputs(func)
        outputs = sdk._infer_outputs(func)

        definition = ToolDefinition(
            name=name,
            description=description or func.__doc__ or "",
            version=version,
            inputs=inputs,
            outputs=outputs,
            category=category,
            tags=tags or [],
            capability=capability or category,
            permission=permission,
            risk_level=risk_level,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            is_idempotent=is_idempotent,
            is_streaming=is_streaming,
            handler=func,
        )

        _standalone_state.created.append(definition)
        logger.info(f"Standalone tool created: {name}")
        return func

    return decorator
