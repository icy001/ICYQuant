"""Workflow Factory — creates workflow definitions programmatically.

The :class:`WorkflowFactory` provides convenience methods for creating common
workflow patterns: linear pipelines, fork-join, and decision trees.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .workflow_definition import WorkflowDefinition
from .workflow_builder import WorkflowBuilder
from .models.node import NodeType

logger = logging.getLogger(__name__)


class WorkflowFactory:
    """Factory for creating common workflow patterns.

    Provides pre-built templates for:
    * Linear pipelines (sequential task chains)
    * Fork-Join (parallel fan-out / fan-in)
    * Decision trees (conditional branching)
    """

    # ------------------------------------------------------------------
    # Linear pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def linear_pipeline(
        name: str,
        tasks: List[Dict[str, Any]],
        *,
        version: str = "1.0.0",
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowDefinition:
        """Create a linear (sequential) workflow from a list of tasks.

        Each task dict should have:
        - node_id (str): unique identifier
        - handler (str): handler name
        - name (str, optional): display name
        - inputs (dict, optional): input parameters

        Example::

            wf = WorkflowFactory.linear_pipeline("data_pipeline", [
                {"node_id": "extract", "handler": "extract_data"},
                {"node_id": "transform", "handler": "transform_data"},
                {"node_id": "load", "handler": "load_data"},
            ])
        """
        builder = WorkflowBuilder(name, version=version)
        if config:
            builder.config(**config)

        node_ids = [t["node_id"] for t in tasks]

        # Add start node
        builder.start_node()

        for task in tasks:
            builder.task_node(
                node_id=task["node_id"],
                handler=task["handler"],
                name=task.get("name"),
                inputs=task.get("inputs", {}),
                max_retries=task.get("max_retries", 0),
                timeout_seconds=task.get("timeout_seconds"),
            )

        # Add end node
        builder.end_node()

        # Chain: start → task1 → task2 → ... → end
        all_ids = ["start"] + node_ids + ["end"]
        builder.chain(*all_ids)

        return builder.build()

    # ------------------------------------------------------------------
    # Fork-Join
    # ------------------------------------------------------------------

    @staticmethod
    def fork_join(
        name: str,
        parallel_tasks: List[Dict[str, Any]],
        *,
        version: str = "1.0.0",
        pre_task: Optional[Dict[str, Any]] = None,
        post_task: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowDefinition:
        """Create a fork-join workflow with parallel execution.

        The workflow structure is::

            start → [pre_task] → fork → [task1, task2, ...] → join → [post_task] → end

        Example::

            wf = WorkflowFactory.fork_join("risk_analysis", [
                {"node_id": "market_risk", "handler": "calc_market_risk"},
                {"node_id": "credit_risk", "handler": "calc_credit_risk"},
                {"node_id": "liquidity_risk", "handler": "calc_liquidity_risk"},
            ])
        """
        builder = WorkflowBuilder(name, version=version)
        if config:
            builder.config(**config)

        builder.start_node()

        # Pre-task (optional)
        if pre_task:
            builder.task_node(
                node_id=pre_task["node_id"],
                handler=pre_task["handler"],
                name=pre_task.get("name"),
                inputs=pre_task.get("inputs", {}),
            )
            builder.edge("start", pre_task["node_id"])
            fork_source = pre_task["node_id"]
        else:
            fork_source = "start"

        # Fork node
        builder.fork_node("fork")
        builder.edge(fork_source, "fork")

        # Parallel tasks
        task_ids = []
        for task in parallel_tasks:
            builder.task_node(
                node_id=task["node_id"],
                handler=task["handler"],
                name=task.get("name"),
                inputs=task.get("inputs", {}),
                max_retries=task.get("max_retries", 0),
                timeout_seconds=task.get("timeout_seconds"),
            )
            task_ids.append(task["node_id"])
            builder.edge("fork", task["node_id"])

        # Join node
        builder.join_node("join")
        for task_id in task_ids:
            builder.edge(task_id, "join")

        # Post-task (optional)
        if post_task:
            builder.task_node(
                node_id=post_task["node_id"],
                handler=post_task["handler"],
                name=post_task.get("name"),
                inputs=post_task.get("inputs", {}),
            )
            builder.edge("join", post_task["node_id"])
            builder.edge(post_task["node_id"], "end")
        else:
            builder.edge("join", "end")

        builder.end_node()
        return builder.build()

    # ------------------------------------------------------------------
    # Decision tree
    # ------------------------------------------------------------------

    @staticmethod
    def decision_tree(
        name: str,
        decision_node_id: str,
        condition: str,
        true_branch_tasks: List[Dict[str, Any]],
        false_branch_tasks: List[Dict[str, Any]],
        *,
        version: str = "1.0.0",
        pre_tasks: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowDefinition:
        """Create a workflow with a conditional branch.

        The workflow structure is::

            start → [pre_tasks] → decision → [true_branch] / [false_branch] → end

        Example::

            wf = WorkflowFactory.decision_tree(
                name="order_routing",
                decision_node_id="check_amount",
                condition="order_amount > 10000",
                true_branch_tasks=[{"node_id": "large_order", "handler": "process_large"}],
                false_branch_tasks=[{"node_id": "small_order", "handler": "process_small"}],
            )
        """
        builder = WorkflowBuilder(name, version=version)
        if config:
            builder.config(**config)

        builder.start_node()

        last_node = "start"

        # Pre-tasks
        if pre_tasks:
            for task in pre_tasks:
                builder.task_node(
                    node_id=task["node_id"],
                    handler=task["handler"],
                    name=task.get("name"),
                    inputs=task.get("inputs", {}),
                )
                builder.edge(last_node, task["node_id"])
                last_node = task["node_id"]

        # Decision node
        builder.decision_node(decision_node_id, condition=condition)
        builder.edge(last_node, decision_node_id)

        # True branch
        for task in true_branch_tasks:
            builder.task_node(
                node_id=task["node_id"],
                handler=task["handler"],
                name=task.get("name"),
                inputs=task.get("inputs", {}),
            )
            if task == true_branch_tasks[0]:
                builder.conditional_edge(decision_node_id, task["node_id"], condition=condition)
            else:
                # Chain within branch
                prev = true_branch_tasks[true_branch_tasks.index(task) - 1]["node_id"]
                builder.edge(prev, task["node_id"])

        # False branch
        for task in false_branch_tasks:
            builder.task_node(
                node_id=task["node_id"],
                handler=task["handler"],
                name=task.get("name"),
                inputs=task.get("inputs", {}),
            )
            if task == false_branch_tasks[0]:
                builder.conditional_edge(decision_node_id, task["node_id"], condition=f"not ({condition})")
            else:
                prev = false_branch_tasks[false_branch_tasks.index(task) - 1]["node_id"]
                builder.edge(prev, task["node_id"])

        # Connect branches to end
        builder.end_node()
        if true_branch_tasks:
            builder.edge(true_branch_tasks[-1]["node_id"], "end")
        if false_branch_tasks:
            builder.edge(false_branch_tasks[-1]["node_id"], "end")

        return builder.build()

    # ------------------------------------------------------------------
    # Custom builder
    # ------------------------------------------------------------------

    @staticmethod
    def builder(name: str, *, version: str = "1.0.0") -> WorkflowBuilder:
        """Return a new :class:`WorkflowBuilder` for custom workflow construction."""
        return WorkflowBuilder(name, version=version)
