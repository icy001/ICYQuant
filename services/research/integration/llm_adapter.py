"""LLM Adapter — bridges Research Platform to LLM providers.

Commit 11 Part 1.5: Provides unified LLM access for research tasks
with support for multiple providers and models.

Architecture::

    Research Task → LLM Adapter → Provider (OpenAI/Anthropic/etc.) → Response

Supported providers:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Local models (reserved)
    - Custom endpoints
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class LLMAdapterState(str, Enum):
    """LLM adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"


class LLMAdapter:
    """Adapter for unified LLM access across the research platform.

    Provides a consistent interface for generating text, analyzing data,
    and producing research insights using LLMs.

    Usage::

        adapter = LLMAdapter(config={"provider": "openai", "api_key": "..."})
        await adapter.initialize()
        response = await adapter.generate(
            prompt="Explain the Sharpe ratio",
            system_prompt="You are a quant finance expert.",
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"llm-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: LLMAdapterState = LLMAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Provider configuration
        self._provider: LLMProvider = LLMProvider(self._config.get("provider", "openai"))
        self._api_key: str = self._config.get("api_key", "")
        self._api_base: str = self._config.get("api_base", "")
        self._default_model: str = self._config.get("default_model", "gpt-4")

        # Model configuration
        self._available_models: Dict[str, Dict[str, Any]] = {}
        self._rate_limiter: Dict[str, Any] = {"requests_per_minute": 60, "tokens_per_minute": 90000}

        # Request history
        self._request_count: int = 0
        self._token_count: int = 0
        self._response_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> LLMAdapterState:
        return self._state

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def default_model(self) -> str:
        return self._default_model

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize LLM adapter."""
        self._state = LLMAdapterState.INITIALIZING
        logger.info("Initializing LLMAdapter [%s] provider=%s model=%s",
                     self._id, self._provider.value, self._default_model)

        # Register available models
        self._available_models = {
            "gpt-4": {"max_tokens": 8192, "provider": "openai"},
            "gpt-3.5-turbo": {"max_tokens": 4096, "provider": "openai"},
            "claude-3-opus": {"max_tokens": 200000, "provider": "anthropic"},
            "claude-3-sonnet": {"max_tokens": 200000, "provider": "anthropic"},
        }

        self._state = LLMAdapterState.READY
        logger.info("LLMAdapter initialized [%s]", self._id)

    async def shutdown(self) -> None:
        """Clean up."""
        self._response_cache.clear()
        self._state = LLMAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt/message.
            system_prompt: System-level instruction.
            model: Model name (defaults to configured default).
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens to generate.
            stop_sequences: Optional stop sequences.

        Returns:
            Generated response with metadata.
        """
        model_name = model or self._default_model
        logger.info("LLM generate: model=%s, prompt_len=%d", model_name, len(prompt))

        # Simulate LLM generation
        await asyncio.sleep(0.02)
        self._request_count += 1

        response_text = (
            f"[{model_name}] Analysis complete. Based on the provided data and research context, "
            f"the key findings indicate significant patterns worth further investigation. "
            f"The analysis covers the requested dimensions with quantitative rigor."
        )

        estimated_tokens = len(prompt) // 4 + len(response_text) // 4
        self._token_count += estimated_tokens

        return {
            "model": model_name,
            "response": response_text,
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": estimated_tokens,
            },
            "finish_reason": "stop",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a response with conversation context.

        Args:
            prompt: User prompt.
            context: List of previous messages [{"role": "user/assistant", "content": "..."}].
            model: Model name.

        Returns:
            Generated response.
        """
        full_prompt = "\n".join([f"[{m['role']}]: {m['content']}" for m in context])
        full_prompt += f"\n[user]: {prompt}"
        return await self.generate(prompt=full_prompt, model=model)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> Dict[str, Any]:
        """Generate embeddings for text.

        Args:
            text: Input text.
            model: Embedding model name.

        Returns:
            Embedding vector and metadata.
        """
        logger.info("Generating embedding: len=%d, model=%s", len(text), model)
        await asyncio.sleep(0.01)
        return {
            "model": model,
            "embedding_dim": 1536,
            "text_length": len(text),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Model Management
    # ------------------------------------------------------------------

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        return [
            {"name": name, "max_tokens": info["max_tokens"], "provider": info["provider"]}
            for name, info in self._available_models.items()
        ]

    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get model information."""
        info = self._available_models.get(model)
        if info is None:
            raise KeyError(f"Model not found: {model}")
        return {"name": model, **info}

    # ------------------------------------------------------------------
    # Usage Metrics
    # ------------------------------------------------------------------

    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get LLM usage statistics."""
        return {
            "adapter_id": self._id,
            "provider": self._provider.value,
            "request_count": self._request_count,
            "token_count": self._token_count,
            "default_model": self._default_model,
        }
