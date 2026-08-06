"""AI Runtime Adapter — bridges Research Platform to the AI Runtime.

Commit 11 Part 1.5: Integrates AI capabilities (LLM, agents, tools) into
the research platform for AI-augmented factor discovery, strategy analysis,
report generation, and data exploration.

Architecture::

    Research → LLM → Agent → Tool → Result

Capabilities:
    - AI factor discovery
    - AI strategy explanation
    - AI report generation
    - AI data analysis
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AIRuntimeAdapterState(str, Enum):
    """AI runtime adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AITaskType(str, Enum):
    """Types of AI-augmented research tasks."""

    FACTOR_DISCOVERY = "factor_discovery"
    STRATEGY_EXPLANATION = "strategy_explanation"
    REPORT_GENERATION = "report_generation"
    DATA_ANALYSIS = "data_analysis"
    MARKET_SUMMARY = "market_summary"
    RISK_ANALYSIS = "risk_analysis"
    CUSTOM = "custom"


class AIRuntimeAdapter:
    """Adapter for integrating Research Platform with AI Runtime.

    Provides AI-augmented research capabilities including LLM-based
    factor discovery, strategy explanation, and report generation.

    Usage::

        adapter = AIRuntimeAdapter(config={"ai_runtime_url": "..."})
        await adapter.initialize()
        report = await adapter.generate_research_report(
            topic="US Tech Sector Analysis",
            data={"sector": "Technology", "period": "Q1 2024"},
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"aira-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: AIRuntimeAdapterState = AIRuntimeAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # AI runtime connection
        self._ai_runtime_url: str = self._config.get("ai_runtime_url", "http://localhost:8800")
        self._ai_runtime_connected: bool = False

        # LLM and Agent references
        self._llm_adapter: Any = None
        self._agent_adapter: Any = None

        # Task history
        self._task_history: List[Dict[str, Any]] = []
        self._default_model: str = self._config.get("default_model", "gpt-4")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> AIRuntimeAdapterState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._ai_runtime_connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize AI runtime adapter."""
        self._state = AIRuntimeAdapterState.INITIALIZING
        logger.info("Initializing AIRuntimeAdapter [%s] → %s", self._id, self._ai_runtime_url)

        try:
            from .llm_adapter import LLMAdapter
            from .agent_adapter import AgentAdapter

            self._llm_adapter = LLMAdapter(config=self._config)
            await self._llm_adapter.initialize()

            self._agent_adapter = AgentAdapter(config=self._config)
            await self._agent_adapter.initialize()

            await self._connect()
            self._ai_runtime_connected = True
            self._state = AIRuntimeAdapterState.CONNECTED
        except Exception as exc:
            logger.error("Failed to initialize AI Runtime: %s", exc)
            self._state = AIRuntimeAdapterState.ERROR
            raise

        logger.info("AIRuntimeAdapter initialized [%s] model=%s", self._id, self._default_model)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with the AI Runtime."""
        return {
            "adapter_id": self._id,
            "ai_runtime_connected": self._ai_runtime_connected,
            "default_model": self._default_model,
            "task_history_size": len(self._task_history),
        }

    async def shutdown(self) -> None:
        """Disconnect from AI runtime and clean up."""
        logger.info("Shutting down AIRuntimeAdapter [%s]...", self._id)
        if self._llm_adapter is not None:
            await self._llm_adapter.shutdown()
        if self._agent_adapter is not None:
            await self._agent_adapter.shutdown()
        self._ai_runtime_connected = False
        self._state = AIRuntimeAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish connection to AI Runtime."""
        logger.info("Connecting to AI Runtime at %s", self._ai_runtime_url)
        await asyncio.sleep(0.01)
        logger.info("Connected to AI Runtime")

    # ------------------------------------------------------------------
    # AI Research Tasks
    # ------------------------------------------------------------------

    async def execute_ai_task(
        self,
        task_type: AITaskType,
        prompt: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Execute an AI-augmented research task.

        Args:
            task_type: Type of AI task.
            prompt: Task prompt/instruction.
            data: Contextual data for the task.
            model: Model to use (default: from config).
            temperature: Generation temperature.

        Returns:
            AI-generated result.
        """
        task_id = f"ait-{uuid4().hex[:12]}"
        task = {
            "id": task_id,
            "type": task_type.value,
            "prompt": prompt,
            "data": data or {},
            "model": model or self._default_model,
            "temperature": temperature,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Execute via LLM adapter
        if self._llm_adapter is not None:
            result = await self._llm_adapter.generate(
                prompt=prompt,
                system_prompt=self._get_system_prompt(task_type),
                model=model or self._default_model,
                temperature=temperature,
            )
            task["result"] = result
        else:
            task["result"] = "AI Runtime not available"

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._task_history.append(task)

        logger.info("AI task completed: %s [%s]", task_id, task_type.value)
        return task

    def _get_system_prompt(self, task_type: AITaskType) -> str:
        """Get appropriate system prompt for each task type."""
        prompts = {
            AITaskType.FACTOR_DISCOVERY: (
                "You are a quantitative research assistant specialized in alpha factor "
                "discovery. Analyze market data and propose novel alpha factors with "
                "sound economic rationale."
            ),
            AITaskType.STRATEGY_EXPLANATION: (
                "You are a quantitative strategy analyst. Explain trading strategies "
                "clearly, including their logic, risk factors, and expected behavior "
                "in different market regimes."
            ),
            AITaskType.REPORT_GENERATION: (
                "You are a financial research report writer. Generate professional, "
                "data-driven research reports with clear structure and actionable insights."
            ),
            AITaskType.DATA_ANALYSIS: (
                "You are a quantitative data analyst. Analyze financial data and provide "
                "statistical insights, patterns, and anomalies."
            ),
            AITaskType.MARKET_SUMMARY: (
                "You are a market strategist. Summarize market conditions, identify key "
                "drivers, and provide forward-looking analysis."
            ),
            AITaskType.RISK_ANALYSIS: (
                "You are a risk management specialist. Analyze portfolio risk metrics "
                "and provide risk mitigation recommendations."
            ),
            AITaskType.CUSTOM: (
                "You are a quantitative research assistant. Help with research tasks "
                "accurately and insightfully."
            ),
        }
        return prompts.get(task_type, prompts[AITaskType.CUSTOM])

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    async def discover_factors(self, market_context: Dict[str, Any]) -> Dict[str, Any]:
        """AI-assisted factor discovery."""
        return await self.execute_ai_task(
            task_type=AITaskType.FACTOR_DISCOVERY,
            prompt=f"Propose novel alpha factors based on: {market_context}",
            data=market_context,
        )

    async def explain_strategy(self, strategy_id: str, backtest_results: Dict[str, Any]) -> Dict[str, Any]:
        """AI-powered strategy explanation."""
        return await self.execute_ai_task(
            task_type=AITaskType.STRATEGY_EXPLANATION,
            prompt=f"Explain strategy '{strategy_id}' given results: {backtest_results}",
            data={"strategy_id": strategy_id, "results": backtest_results},
        )

    async def generate_research_report(self, topic: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI research report."""
        return await self.execute_ai_task(
            task_type=AITaskType.REPORT_GENERATION,
            prompt=f"Generate a research report on: {topic}",
            data=data,
        )

    async def analyze_data(self, dataset_id: str, query: str) -> Dict[str, Any]:
        """AI-powered data analysis."""
        return await self.execute_ai_task(
            task_type=AITaskType.DATA_ANALYSIS,
            prompt=f"Analyze dataset '{dataset_id}': {query}",
            data={"dataset_id": dataset_id, "query": query},
        )

    # ------------------------------------------------------------------
    # Task History
    # ------------------------------------------------------------------

    async def get_task_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent AI task history."""
        return self._task_history[-limit:]

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific AI task result."""
        for task in self._task_history:
            if task["id"] == task_id:
                return dict(task)
        raise KeyError(f"Task not found: {task_id}")
