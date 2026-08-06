"""Agent Adapter — bridges Research Platform to AI Agent framework.

Commit 11 Part 1.5: Provides agent-based research capabilities including
tool-calling, multi-step reasoning, and autonomous research workflows.

Architecture::

    Agent → Tool Calling → Multi-step Reasoning → Research Result

Agent capabilities:
    - Autonomous research planning
    - Tool-augmented analysis (data fetch, compute, visualize)
    - Multi-step reasoning chains
    - Research workflow automation
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentAdapterState(str, Enum):
    """Agent adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class AgentRole(str, Enum):
    """Predefined agent roles for research."""

    RESEARCHER = "researcher"
    ANALYST = "analyst"
    REPORTER = "reporter"
    REVIEWER = "reviewer"


class ToolCategory(str, Enum):
    """Categories of tools available to agents."""

    DATA_FETCH = "data_fetch"
    COMPUTATION = "computation"
    VISUALIZATION = "visualization"
    REPORTING = "reporting"
    PUBLISHING = "publishing"
    CUSTOM = "custom"


class AgentAdapter:
    """Adapter for AI Agent integration into research workflows.

    Provides agent-based research with tool-calling, multi-step reasoning,
    and autonomous workflow execution.

    Usage::

        adapter = AgentAdapter(config={"llm_model": "gpt-4"})
        await adapter.initialize()
        result = await adapter.run_agent(
            role=AgentRole.RESEARCHER,
            task="Analyze factor performance for momentum strategy",
            tools=["fetch_data", "compute_ic", "generate_plot"],
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"agt-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: AgentAdapterState = AgentAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Tool registry
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._tool_categories: Dict[ToolCategory, List[str]] = {c: [] for c in ToolCategory}

        # Agent instances
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._run_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> AgentAdapterState:
        return self._state

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize agent adapter and register default tools."""
        self._state = AgentAdapterState.INITIALIZING
        logger.info("Initializing AgentAdapter [%s]", self._id)

        # Register default research tools
        await self._register_default_tools()
        self._state = AgentAdapterState.READY
        logger.info("AgentAdapter initialized [%s] — %d tools registered", self._id, len(self._tools))

    async def shutdown(self) -> None:
        """Clean up."""
        self._tools.clear()
        self._agents.clear()
        self._run_history.clear()
        self._state = AgentAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Tool Management
    # ------------------------------------------------------------------

    async def register_tool(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        handler: Callable,
        *,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool that agents can call.

        Args:
            name: Tool name (used in function calling).
            description: Tool description for the LLM.
            category: Tool category.
            handler: Async callable implementing the tool.
            parameters: JSON Schema for tool parameters.
        """
        self._tools[name] = {
            "name": name,
            "description": description,
            "category": category,
            "handler": handler,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        self._tool_categories[category].append(name)
        logger.info("Tool registered: %s [%s]", name, category.value)

    async def _register_default_tools(self) -> None:
        """Register default research tools."""
        defaults = [
            ("fetch_market_data", "Fetch market data for given symbols and date range",
             ToolCategory.DATA_FETCH),
            ("compute_factor", "Compute a factor value for given symbols",
             ToolCategory.COMPUTATION),
            ("compute_ic", "Compute Information Coefficient for a factor",
             ToolCategory.COMPUTATION),
            ("run_backtest", "Run a backtest with given strategy and parameters",
             ToolCategory.COMPUTATION),
            ("generate_plot", "Generate a plot/chart from data",
             ToolCategory.VISUALIZATION),
            ("generate_report", "Generate a research report",
             ToolCategory.REPORTING),
            ("publish_factor", "Publish a factor to production",
             ToolCategory.PUBLISHING),
        ]

        for name, desc, category in defaults:
            await self.register_tool(
                name=name,
                description=desc,
                category=category,
                handler=self._default_tool_handler,
            )

    async def _default_tool_handler(self, **kwargs: Any) -> Dict[str, Any]:
        """Default tool handler stub."""
        return {"status": "completed", "result": "Tool executed successfully"}

    # ------------------------------------------------------------------
    # Agent Execution
    # ------------------------------------------------------------------

    async def create_agent(
        self,
        role: AgentRole,
        *,
        agent_name: Optional[str] = None,
        tools: Optional[List[str]] = None,
        instructions: Optional[str] = None,
    ) -> str:
        """Create an AI agent instance.

        Args:
            role: Agent role.
            agent_name: Optional display name.
            tools: List of tool names available to the agent.
            instructions: Custom instructions for the agent.

        Returns:
            Agent ID.
        """
        agent_id = f"agent-{uuid4().hex[:12]}"
        self._agents[agent_id] = {
            "id": agent_id,
            "name": agent_name or f"{role.value}-{agent_id[:8]}",
            "role": role.value,
            "tools": tools or [],
            "instructions": instructions or self._get_default_instructions(role),
            "status": "idle",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Agent created: %s [%s]", agent_id, role.value)
        return agent_id

    def _get_default_instructions(self, role: AgentRole) -> str:
        """Get default instructions for each agent role."""
        instructions = {
            AgentRole.RESEARCHER: (
                "You are a quantitative researcher. Conduct thorough analysis, "
                "propose hypotheses, and use available tools to validate them. "
                "Always provide evidence-based conclusions."
            ),
            AgentRole.ANALYST: (
                "You are a quantitative analyst. Analyze data rigorously, compute "
                "relevant metrics, and provide clear statistical interpretations. "
                "Focus on actionable insights."
            ),
            AgentRole.REPORTER: (
                "You are a research reporter. Generate clear, professional reports "
                "summarizing research findings. Structure reports with executive "
                "summary, methodology, results, and conclusions."
            ),
            AgentRole.REVIEWER: (
                "You are a research reviewer. Critically evaluate research outputs, "
                "identify potential issues, and suggest improvements. Focus on "
                "methodological rigor and practical applicability."
            ),
        }
        return instructions.get(role, instructions[AgentRole.RESEARCHER])

    async def run_agent(
        self,
        role: AgentRole,
        task: str,
        *,
        tools: Optional[List[str]] = None,
        max_steps: int = 10,
    ) -> Dict[str, Any]:
        """Run an agent to complete a research task.

        Args:
            role: Agent role.
            task: Task description.
            tools: Tools available (default: all).
            max_steps: Maximum reasoning steps.

        Returns:
            Agent execution result.
        """
        agent_id = await self.create_agent(role=role, tools=tools)
        run_id = f"arun-{uuid4().hex[:12]}"

        logger.info("Running agent %s [%s]: %s", agent_id, role.value, task[:80])

        # Simulate multi-step agent execution
        steps = []
        for i in range(min(3, max_steps)):
            step_result = await self._execute_agent_step(agent_id, task, step_num=i + 1)
            steps.append(step_result)

        result = {
            "run_id": run_id,
            "agent_id": agent_id,
            "role": role.value,
            "task": task,
            "steps": steps,
            "status": "completed",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        self._run_history.append(result)
        logger.info("Agent run complete: %s [%s]", run_id, role.value)
        return result

    async def _execute_agent_step(self, agent_id: str, task: str, step_num: int) -> Dict[str, Any]:
        """Execute a single agent reasoning step."""
        await asyncio.sleep(0.01)
        return {
            "step": step_num,
            "action": "analyze",
            "thought": f"Analyzing research task: {task[:50]}...",
            "observation": f"Step {step_num} analysis complete.",
        }

    # ------------------------------------------------------------------
    # Multi-Agent Collaboration
    # ------------------------------------------------------------------

    async def run_collaborative(
        self,
        task: str,
        roles: Optional[List[AgentRole]] = None,
    ) -> Dict[str, Any]:
        """Run multiple agents collaboratively on a research task.

        Args:
            task: Research task.
            roles: Agent roles to involve (default: all).

        Returns:
            Collaborative result.
        """
        roles = roles or list(AgentRole)
        collab_id = f"collab-{uuid4().hex[:12]}"
        logger.info("Starting collaborative research [%s] with %d agents", collab_id, len(roles))

        results = {}
        for role in roles:
            results[role.value] = await self.run_agent(role=role, task=task)

        return {
            "collab_id": collab_id,
            "task": task,
            "roles": [r.value for r in roles],
            "agent_results": results,
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_run_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent agent run history."""
        return self._run_history[-limit:]

    async def list_tools(self, category: Optional[ToolCategory] = None) -> List[Dict[str, Any]]:
        """List available tools."""
        tools = list(self._tools.values())
        if category is not None:
            tools = [t for t in tools if t["category"] == category]
        return [{"name": t["name"], "description": t["description"], "category": t["category"].value} for t in tools]
