"""Guardrail Engine — safety and governance guardrails for all AI operations.

The GuardrailEngine sits between the Gateway and the ControlPlane, inspecting
every request and response for safety, compliance, and quality. It enforces
content policies, prevents prompt injection, filters sensitive outputs, and
ensures all operations stay within defined boundaries.

Guardrail layers:
    1. Input guardrails (prompt safety, injection detection)
    2. Tool guardrails (allowed tools, parameter validation)
    3. Output guardrails (content filtering, PII redaction)
    4. Execution guardrails (timeout, resource limits)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class GuardrailVerdict(str, Enum):
    """Verdict from a guardrail check."""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    verdict: GuardrailVerdict = GuardrailVerdict.PASS
    rule_name: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


class GuardrailEngine:
    """Safety and governance guardrails for all AI operations.

    Inspects every request and response through multiple guardrail layers
    to ensure safety, compliance, and quality standards are met.

    Usage:
        ge = GuardrailEngine()
        await ge.initialize()
        ge.add_input_guardrail("no_pii", lambda text: GuardrailResult(verdict=GuardrailVerdict.PASS))
        result = await ge.check_input(user_input)
    """

    # Patterns for PII detection
    _EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    _PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
    _SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')

    def __init__(self) -> None:
        self._input_guardrails: List[Callable] = []
        self._output_guardrails: List[Callable] = []
        self._tool_guardrails: Dict[str, List[Callable]] = {}
        self._execution_guardrails: List[Callable] = []
        self._total_checks: int = 0
        self._total_blocks: int = 0
        self._total_warns: int = 0
        self._initialized: bool = False
        logger.info("GuardrailEngine created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        # Register built-in guardrails
        self.add_input_guardrail("pii_detection", self._check_pii)
        self.add_input_guardrail("injection_detection", self._check_injection)
        self._initialized = True
        logger.info("GuardrailEngine initialized with %d built-in guardrails", 2)

    async def shutdown(self) -> None:
        self._input_guardrails.clear()
        self._output_guardrails.clear()
        self._tool_guardrails.clear()
        self._execution_guardrails.clear()
        self._initialized = False
        logger.info("GuardrailEngine shutdown complete")

    def add_input_guardrail(self, name: str, guardrail_fn: Callable) -> None:
        """Register an input guardrail."""
        self._input_guardrails.append(guardrail_fn)
        logger.info("GuardrailEngine: registered input guardrail '%s'", name)

    def add_output_guardrail(self, name: str, guardrail_fn: Callable) -> None:
        """Register an output guardrail."""
        self._output_guardrails.append(guardrail_fn)
        logger.info("GuardrailEngine: registered output guardrail '%s'", name)

    def add_tool_guardrail(self, tool_name: str, guardrail_fn: Callable) -> None:
        """Register a tool-specific guardrail."""
        self._tool_guardrails.setdefault(tool_name, []).append(guardrail_fn)
        logger.info("GuardrailEngine: registered tool guardrail for '%s'", tool_name)

    async def check_input(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> List[GuardrailResult]:
        """Run all input guardrails against user input."""
        return await self._run_guardrails(self._input_guardrails, user_input, context or {})

    async def check_output(self, ai_output: str, context: Optional[Dict[str, Any]] = None) -> List[GuardrailResult]:
        """Run all output guardrails against AI output."""
        return await self._run_guardrails(self._output_guardrails, ai_output, context or {})

    async def check_tool(self, tool_name: str, tool_params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[GuardrailResult]:
        """Run tool-specific guardrails."""
        guardrails = self._tool_guardrails.get(tool_name, [])
        return await self._run_guardrails(guardrails, tool_params, context or {})

    async def check_execution(self, execution_context: Dict[str, Any]) -> List[GuardrailResult]:
        """Run execution guardrails."""
        return await self._run_guardrails(self._execution_guardrails, execution_context, {})

    async def _run_guardrails(self, guardrails: List[Callable], data: Any, context: Dict[str, Any]) -> List[GuardrailResult]:
        """Execute a list of guardrail functions."""
        results: List[GuardrailResult] = []
        for guardrail_fn in guardrails:
            start = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(guardrail_fn):
                    result = await guardrail_fn(data, context)
                else:
                    result = guardrail_fn(data, context)
                if isinstance(result, GuardrailResult):
                    result.latency_ms = (time.monotonic() - start) * 1000
                    results.append(result)
                    self._total_checks += 1
                    if result.verdict == GuardrailVerdict.BLOCK:
                        self._total_blocks += 1
                    elif result.verdict == GuardrailVerdict.WARN:
                        self._total_warns += 1
            except Exception as e:
                logger.error("GuardrailEngine: guardrail execution error: %s", e)
                results.append(GuardrailResult(verdict=GuardrailVerdict.BLOCK, rule_name="guardrail_error", message=str(e)))
        return results

    def is_blocked(self, results: List[GuardrailResult]) -> bool:
        """Check if any guardrail result is a BLOCK."""
        return any(r.verdict == GuardrailVerdict.BLOCK for r in results)

    def has_warnings(self, results: List[GuardrailResult]) -> bool:
        """Check if any guardrail result is a WARN."""
        return any(r.verdict == GuardrailVerdict.WARN for r in results)

    # ── Built-in Guardrails ──

    def _check_pii(self, text: str, context: Dict[str, Any]) -> GuardrailResult:
        """Check for PII in text."""
        if not isinstance(text, str):
            return GuardrailResult(verdict=GuardrailVerdict.PASS, rule_name="pii_detection")
        emails = self._EMAIL_PATTERN.findall(text)
        phones = self._PHONE_PATTERN.findall(text)
        ssns = self._SSN_PATTERN.findall(text)
        if emails or phones or ssns:
            found = []
            if emails: found.append(f"{len(emails)} email(s)")
            if phones: found.append(f"{len(phones)} phone(s)")
            if ssns: found.append(f"{len(ssns)} SSN(s)")
            return GuardrailResult(
                verdict=GuardrailVerdict.WARN,
                rule_name="pii_detection",
                message=f"Potential PII detected: {', '.join(found)}",
                details={"emails": emails, "phones": phones, "ssns": ssns},
            )
        return GuardrailResult(verdict=GuardrailVerdict.PASS, rule_name="pii_detection")

    def _check_injection(self, text: str, context: Dict[str, Any]) -> GuardrailResult:
        """Check for prompt injection patterns."""
        if not isinstance(text, str):
            return GuardrailResult(verdict=GuardrailVerdict.PASS, rule_name="injection_detection")
        injection_patterns = [
            "ignore previous instructions",
            "ignore all previous",
            "disregard prior",
            "system prompt:",
            "you are now",
            "new instructions:",
            "forget everything",
        ]
        lower_text = text.lower()
        for pattern in injection_patterns:
            if pattern in lower_text:
                return GuardrailResult(
                    verdict=GuardrailVerdict.BLOCK,
                    rule_name="injection_detection",
                    message=f"Potential prompt injection detected: '{pattern}'",
                    details={"pattern": pattern},
                )
        return GuardrailResult(verdict=GuardrailVerdict.PASS, rule_name="injection_detection")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "input_guardrails": len(self._input_guardrails),
            "output_guardrails": len(self._output_guardrails),
            "tool_guardrails": sum(len(v) for v in self._tool_guardrails.values()),
            "execution_guardrails": len(self._execution_guardrails),
            "total_checks": self._total_checks,
            "total_blocks": self._total_blocks,
            "total_warns": self._total_warns,
        }
