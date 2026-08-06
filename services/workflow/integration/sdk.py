"""Workflow SDK — Python SDK for interacting with the ICYQuant workflow engine.

Usage::

    from services.workflow.integration import WorkflowSDK

    sdk = WorkflowSDK(base_url="http://localhost:9090")
    client = sdk.get_client()

    workflow = client.workflow("order_execution")
    await workflow.execute(account="ACC001", symbol="AAPL", quantity=100)

    status = await client.get_status(execution_id)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SDKConfig:
    """Configuration for the workflow SDK client."""

    base_url: str = "http://localhost:9090"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecutionResult:
    """Result of a workflow execution via the SDK."""

    execution_id: str
    workflow_id: str
    status: str = "PENDING"
    output: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class WorkflowHandle:
    """A handle to a specific workflow, providing a fluent execution API."""

    def __init__(self, client: WorkflowClient, workflow_id: str) -> None:
        self._client = client
        self._workflow_id = workflow_id

    @property
    def workflow_id(self) -> str:
        return self._workflow_id

    async def execute(self, **inputs: Any) -> WorkflowExecutionResult:
        """Execute this workflow with the provided inputs."""
        return await self._client.execute(self._workflow_id, **inputs)

    async def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        return await self._client.get_status(execution_id)

    def __repr__(self) -> str:
        return f"WorkflowHandle(id={self._workflow_id!r})"


class WorkflowClient:
    """Client for interacting with the workflow engine.

    Usage::

        client = WorkflowClient(config=SDKConfig(base_url="http://localhost:9090"))
        handle = client.workflow("order_execution")
        result = await handle.execute(account="ACC001")
    """

    def __init__(self, *, config: Optional[SDKConfig] = None) -> None:
        self._config = config or SDKConfig()

    def workflow(self, workflow_id: str) -> WorkflowHandle:
        """Get a handle to a specific workflow."""
        return WorkflowHandle(self, workflow_id)

    async def execute(self, workflow_id: str, **inputs: Any) -> WorkflowExecutionResult:
        """Execute a workflow with the given inputs."""
        execution_id = str(uuid.uuid4())
        logger.info("WorkflowClient: executing %s (execution=%s)", workflow_id, execution_id)
        # In production: POST to /workflow/execute
        return WorkflowExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="PENDING",
            output=inputs,
            started_at=datetime.utcnow(),
        )

    async def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of an execution."""
        # In production: GET /workflow/execution/{execution_id}
        return {"execution_id": execution_id, "status": "UNKNOWN"}

    async def cancel(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        logger.info("WorkflowClient: cancelling %s", execution_id)
        return True

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows."""
        return []

    async def list_executions(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List executions, optionally filtered."""
        return []


class WorkflowSDK:
    """Top-level entry point for the workflow Python SDK.

    Usage::

        sdk = WorkflowSDK(base_url="http://localhost:9090")
        client = sdk.get_client()
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:9090",
        api_key: Optional[str] = None,
    ) -> None:
        self._config = SDKConfig(base_url=base_url, api_key=api_key)
        self._client: Optional[WorkflowClient] = None

    def get_client(self) -> WorkflowClient:
        if self._client is None:
            self._client = WorkflowClient(config=self._config)
        return self._client

    def workflow(self, workflow_id: str) -> WorkflowHandle:
        return self.get_client().workflow(workflow_id)

    @property
    def config(self) -> SDKConfig:
        return self._config
