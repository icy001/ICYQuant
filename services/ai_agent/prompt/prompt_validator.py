"""
Prompt validator for quality assurance and compliance.

Validates prompt content for length, format, safety,
and structural integrity before LLM delivery.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptValidator:
    """Validates prompt content before LLM delivery.

    Checks for:
        - Length constraints
        - Required structure elements
        - Unsafe or prohibited content
        - Variable completeness
        - Format validation

    Usage:
        validator = PromptValidator()
        result = validator.validate(prompt_content, max_length=8000)
        if result["valid"]:
            send_to_llm(prompt_content)
    """

    def __init__(self) -> None:
        self._validation_count: int = 0
        self._fail_count: int = 0
        logger.info("PromptValidator created")

    # ── Validation ──

    def validate(
        self,
        content: str,
        max_length: int = 8000,
        required_sections: Optional[List[str]] = None,
        prohibited_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Validate a prompt string.

        Args:
            content: The prompt content to validate.
            max_length: Maximum allowed character count.
            required_sections: Optional list of required section headers.
            prohibited_patterns: Optional regex patterns to block.

        Returns:
            Dict with 'valid' boolean, 'issues' list, and 'warnings' list.
        """
        self._validation_count += 1
        issues: List[str] = []
        warnings: List[str] = []

        # Check 1: Non-empty
        if not content or not content.strip():
            issues.append("Prompt content is empty")
            self._fail_count += 1
            return self._result(False, issues, warnings)

        # Check 2: Length
        if len(content) > max_length:
            issues.append(f"Prompt exceeds max length: {len(content)} > {max_length}")
        if len(content) < 10:
            warnings.append("Prompt is very short, may lack sufficient context")

        # Check 3: Required sections
        if required_sections:
            for section in required_sections:
                if section.lower() not in content.lower():
                    issues.append(f"Missing required section: {section}")

        # Check 4: Prohibited patterns
        if prohibited_patterns:
            for pattern in prohibited_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(f"Prompt contains prohibited pattern: {pattern}")

        # Check 5: Basic structure
        structure_issues = self._check_structure(content)
        warnings.extend(structure_issues)

        # Check 6: Unresolved variables
        unresolved = re.findall(r"\{\{\s*\w+\s*\}\}", content)
        if unresolved:
            warnings.append(f"Prompt contains unresolved variables: {unresolved}")

        is_valid = len(issues) == 0
        if not is_valid:
            self._fail_count += 1

        return self._result(is_valid, issues, warnings)

    def _check_structure(self, content: str) -> List[str]:
        """Check prompt structural integrity."""
        warnings: List[str] = []

        lines = content.split("\n")
        if len(lines) < 2:
            warnings.append("Very short prompt, consider adding more context")

        # Check for extremely long lines
        for i, line in enumerate(lines):
            if len(line) > 2000:
                warnings.append(f"Line {i+1} is very long ({len(line)} chars)")

        return warnings

    def _result(
        self,
        valid: bool,
        issues: List[str],
        warnings: List[str],
    ) -> Dict[str, Any]:
        """Build validation result dict."""
        return {
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
            "issue_count": len(issues),
            "warning_count": len(warnings),
        }

    # ── Quick Checks ──

    def is_valid_length(self, content: str, max_length: int = 8000) -> bool:
        """Quick length check."""
        return 0 < len(content) <= max_length

    def has_variables(self, content: str) -> bool:
        """Check if content has unresolved template variables."""
        return bool(re.search(r"\{\{\s*\w+\s*\}\}", content))

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get validator summary."""
        return {
            "validations_performed": self._validation_count,
            "validations_failed": self._fail_count,
            "pass_rate": (
                1.0 - (self._fail_count / max(self._validation_count, 1))
            ),
        }
