"""Workflow Executor — executes a workflow definition against a context.

The :class:`WorkflowExecutor` is the runtime engine that walks a workflow DAG
node-by-node, managing execution order, parallelism, retries, and timeouts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .workflow_definition import WorkflowDefinition
from .workflow_context import WorkflowContext
from .workflow_runtime import WorkflowRuntime
from .models.node import NodeType, NodeStatus

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes a workflow definition within a runtime context.

    The executor traverses the DAG in dependency order, executing each node
    and collecting results in the shared :class:`WorkflowContext`.
    """

    def __init__(self, *, runtime: WorkflowRuntime) -> None:
        self._runtime = runtime
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("WorkflowExecutor: started")

    async def shutdown(self) -> None:
        self._started = False
        logger.info("WorkflowExecutor: shut down")

    async def execute(
        self,
        *,
        definition: WorkflowDefinition,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """Execute a workflow definition against the given context.

        Returns a dict with execution results.
        """
        if not self._started:
            raise RuntimeError("Executor not started")

        context.set_status("running")
        self._runtime.register_instance(context)
        started_at = datetime.utcnow()

        try:
            # Publish workflow-started event
            await self._runtime.event_bus.publish("workflow_started", {
                "workflow_id": definition.name,
                "execution_id": context.execution_id,
                "version": definition.version,
            })

            # Execute the DAG in topological order
            completed: Set[str] = set()
            failed: Set[str] = set()
            node_results: Dict[str, Any] = {}

            # Build dependency tracking
            indegree: Dict[str, int] = {}
            successors: Dict[str, List[str]] = {}

            for node in definition.nodes:
                indegree[node.node_id] = len(definition.get_incoming_edges(node.node_id))
                successors[node.node_id] = definition.get_successors(node.node_id)

            # Ready queue — nodes with indegree 0
            ready: List[str] = [n.node_id for n in definition.nodes if indegree[n.node_id] == 0]

            while ready:
                # Execute all ready nodes (potentially in parallel)
                node_id = ready.pop(0)

                try:
                    result = await self._execute_node(
                        definition=definition,
                        context=context,
                        node_id=node_id,
                    )
                    node_results[node_id] = result
                    completed.add(node_id)
                    context.set_node_result(node_id, result)

                    # Decrement indegree of successors
                    for succ in successors.get(node_id, []):
                        indegree[succ] -= 1
                        if indegree[succ] == 0:
                            ready.append(succ)

                except asyncio.CancelledError:
                    context.set_status("cancelled")
                    raise
                except Exception as exc:
                    failed.add(node_id)
                    logger.error("Node %s failed: %s", node_id, exc, exc_info=True)
                    # Check if we should continue or abort
                    node = definition.get_node(node_id)
                    if node and node.config.continue_on_failure:
                        completed.add(node_id)
                        for succ in successors.get(node_id, []):
                            indegree[succ] -= 1
                            if indegree[succ] == 0:
                                ready.append(succ)
                    else:
                        context.set_status("failed")
                        context.set_metadata("error", str(exc))
                        context.set_metadata("failed_node", node_id)
                        break

            # Determine final status
            if context.status == "cancelled":
                pass  # already set
            elif failed:
                context.set_status("failed")
            elif len(completed) == definition.node_count:
                context.set_status("completed")
            else:
                context.set_status("failed")
                context.set_metadata("error", "Workflow did not complete all nodes")

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Publish workflow-completed event
            await self._runtime.event_bus.publish("workflow_completed", {
                "workflow_id": definition.name,
                "execution_id": context.execution_id,
                "status": context.status,
                "completed_nodes": len(completed),
                "failed_nodes": len(failed),
                "duration_seconds": duration,
            })

            return {
                "execution_id": context.execution_id,
                "status": context.status,
                "completed_nodes": list(completed),
                "failed_nodes": list(failed),
                "node_results": node_results,
                "duration_seconds": duration,
            }

        finally:
            self._runtime.unregister_instance(context.execution_id)

    async def _execute_node(
        self,
        *,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        node_id: str,
    ) -> Any:
        """Execute a single node and return its result."""
        node = definition.get_node(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")

        logger.debug("Executing node %s (type=%s)", node_id, node.node_type.value)

        # Publish node-started event
        await self._runtime.event_bus.publish("node_started", {
            "workflow_id": definition.name,
            "execution_id": context.execution_id,
            "node_id": node_id,
            "node_type": node.node_type.value,
        })

        result = None

        # Execute based on node type
        if node.node_type == NodeType.START:
            result = {"started": True}
        elif node.node_type == NodeType.END:
            result = {"completed": True}
        elif node.node_type == NodeType.TASK:
            result = await self._execute_task(node, context)
        elif node.node_type == NodeType.DECISION:
            result = await self._execute_decision(node, context)
        elif node.node_type == NodeType.FORK:
            result = await self._execute_fork(node, context)
        elif node.node_type == NodeType.JOIN:
            result = await self._execute_join(node, context)
        elif node.node_type == NodeType.WAIT:
            result = await self._execute_wait(node, context)
        elif node.node_type == NodeType.SCRIPT:
            result = await self._execute_script(node, context)
        elif node.node_type == NodeType.SERVICE:
            result = await self._execute_service(node, context)
        elif node.node_type == NodeType.SUB_WORKFLOW:
            result = await self._execute_sub_workflow(node, context)
        else:
            result = {"node_id": node_id, "type": node.node_type.value}

        # Publish node-completed event
        await self._runtime.event_bus.publish("node_completed", {
            "workflow_id": definition.name,
            "execution_id": context.execution_id,
            "node_id": node_id,
            "node_type": node.node_type.value,
            "result": str(result)[:200],
        })

        return result

    # ------------------------------------------------------------------
    # Node type executors
    # ------------------------------------------------------------------

    async def _execute_task(self, node, context: WorkflowContext) -> Any:
        """Execute a task node with optional timeout and retries."""
        timeout = node.config.timeout_seconds
        max_retries = node.config.max_retries

        for attempt in range(max_retries + 1):
            try:
                if timeout:
                    result = await asyncio.wait_for(
                        self._run_handler(node, context),
                        timeout=timeout,
                    )
                else:
                    result = await self._run_handler(node, context)
                return result
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    logger.warning("Node %s timed out (attempt %d/%d)", node.node_id, attempt + 1, max_retries + 1)
                    await asyncio.sleep(node.config.retry_delay_seconds)
                else:
                    raise
            except Exception:
                if attempt < max_retries:
                    logger.warning("Node %s failed (attempt %d/%d)", node.node_id, attempt + 1, max_retries + 1)
                    await asyncio.sleep(node.config.retry_delay_seconds)
                else:
                    raise

    async def _execute_decision(self, node, context: WorkflowContext) -> Any:
        """Execute a decision node — evaluates condition and returns branch info."""
        condition = node.config.condition
        if condition:
            # Evaluate condition against context variables
            try:
                result = self._evaluate_condition(condition, context)
                return {"decision": result, "condition": condition}
            except Exception:
                return {"decision": False, "condition": condition, "error": "evaluation_failed"}
        return {"decision": True}

    async def _execute_fork(self, node, context: WorkflowContext) -> Any:
        """Fork execution — marker node, actual parallelism handled by scheduler."""
        return {"forked": True}

    async def _execute_join(self, node, context: WorkflowContext) -> Any:
        """Join execution — marker node, synchronization handled by scheduler."""
        return {"joined": True}

    async def _execute_wait(self, node, context: WorkflowContext) -> Any:
        """Execute a wait/delay node."""
        wait_seconds = node.inputs.get("wait_seconds", 1.0)
        await asyncio.sleep(float(wait_seconds))
        return {"waited": wait_seconds}

    async def _execute_script(self, node, context: WorkflowContext) -> Any:
        """Execute a script node."""
        script = node.inputs.get("script", "")
        # Script execution would be handled by a script engine
        return {"script_executed": True, "script": script[:100]}

    async def _execute_service(self, node, context: WorkflowContext) -> Any:
        """Execute a service call node."""
        handler = node.handler
        if handler:
            # Service call would be dispatched via service registry
            return {"service_called": handler, "inputs": dict(node.inputs)}
        return {"service_called": False}

    async def _execute_sub_workflow(self, node, context: WorkflowContext) -> Any:
        """Execute a sub-workflow — placeholder for recursive execution."""
        return {"sub_workflow": True, "node_id": node.node_id}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _run_handler(self, node, context: WorkflowContext) -> Any:
        """Run a node's handler function if available."""
        handler = node.handler
        if handler and hasattr(node, "_handler_fn") and node._handler_fn:
            if asyncio.iscoroutinefunction(node._handler_fn):
                return await node._handler_fn(context, node.inputs)
            else:
                return node._handler_fn(context, node.inputs)
        return {"handler": handler, "inputs": dict(node.inputs)}

    def _evaluate_condition(self, condition: str, context: WorkflowContext) -> bool:
        """Evaluate a simple condition expression against context variables."""
        # Simple expression evaluation: supports basic comparisons
        # Format: "variable operator value" e.g., "order_amount > 1000"
        try:
            parts = condition.strip().split()
            if len(parts) >= 3:
                var_name = parts[0]
                operator = parts[1]
                target = " ".join(parts[2:])

                var_value = context.get_variable(var_name)

                # Try numeric comparison
                try:
                    var_num = float(var_value) if var_value is not None else 0
                    target_num = float(target)
                    if operator == ">":
                        return var_num > target_num
                    elif operator == "<":
                        return var_num < target_num
                    elif operator == ">=":
                        return var_num >= target_num
                    elif operator == "<=":
                        return var_num <= target_num
                    elif operator == "==":
                        return var_num == target_num
                    elif operator == "!=":
                        return var_num != target_num
                except (ValueError, TypeError):
                    pass

                # String comparison
                var_str = str(var_value) if var_value is not None else ""
                if operator == "==":
                    return var_str == target
                elif operator == "!=":
                    return var_str != target
                elif operator == "in":
                    return var_str in target
                elif operator == "contains":
                    return target in var_str

            # Default: truthy check
            return bool(condition)
        except Exception:
            return False
