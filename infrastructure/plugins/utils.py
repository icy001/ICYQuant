"""Plugin utility functions.

Provides helpers for plugin id generation, version comparison,
slugification, configuration merging, and safe module imports
used across the ICYQuant plugin framework.
"""

from __future__ import annotations

import importlib
import uuid
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple


def slugify(text: str) -> str:
    """Convert text to a lowercase hyphenated slug.

    Runs of non-alphanumeric characters are collapsed into single
    hyphens, and leading/trailing hyphens are stripped.
    """
    if not text:
        return ""
    slug: List[str] = []
    prev_hyphen = False
    for ch in text.strip().lower():
        if ch.isalnum():
            slug.append(ch)
            prev_hyphen = False
        else:
            if not prev_hyphen:
                slug.append("-")
                prev_hyphen = True
    return "".join(slug).strip("-")


def generate_plugin_id(name: str) -> str:
    """Generate a plugin id from a plugin name by slugifying it."""
    return slugify(name)


def sanitize_plugin_name(name: str) -> str:
    """Remove special characters from a plugin name.

    Keeps alphanumeric characters, spaces, hyphens, and underscores.
    """
    if not name:
        return ""
    return "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip()


def parse_version(version: str) -> Tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    Handles versions like ``"1.2.3"`` -> ``(1, 2, 3)``. A leading ``v``
    is stripped and non-numeric suffixes (e.g. pre-release tags) are
    dropped per component. Missing components default to ``0`` and the
    result is padded to at least three components.
    """
    if not version:
        return (0, 0, 0)
    cleaned = version.strip().lstrip("vV")
    parts = cleaned.split(".")
    numeric_parts: List[int] = []
    for part in parts:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        numeric_parts.append(int(digits) if digits else 0)
    while len(numeric_parts) < 3:
        numeric_parts.append(0)
    return tuple(numeric_parts)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.

    Returns:
        -1 if ``v1`` < ``v2``, 0 if equal, 1 if ``v1`` > ``v2``.
    """
    p1 = list(parse_version(v1))
    p2 = list(parse_version(v2))
    while len(p1) < len(p2):
        p1.append(0)
    while len(p2) < len(p1):
        p2.append(0)
    if p1 < p2:
        return -1
    if p1 > p2:
        return 1
    return 0


def is_compatible_version(required: str, actual: str) -> bool:
    """Check whether the actual version satisfies the required version.

    Supports plain version strings (``"1.0.0"``) and constraint
    expressions (``">=1.0.0"``, ``"<=2.0.0"``, etc.).
    """
    for op in ("<=", ">=", "!=", "==", "<", ">", "~="):
        if required.startswith(op):
            target = required[len(op):].strip()
            cmp = compare_versions(actual, target)
            if op == ">=":
                return cmp >= 0
            elif op == "<=":
                return cmp <= 0
            elif op == ">":
                return cmp > 0
            elif op == "<":
                return cmp < 0
            elif op == "==":
                return cmp == 0
            elif op == "!=":
                return cmp != 0
            elif op == "~=":
                parts = target.split(".")
                if len(parts) >= 2:
                    prefix = ".".join(parts[:-1])
                    return compare_versions(actual, prefix) >= 0 and compare_versions(actual, target) <= 0
                return compare_versions(actual, target) >= 0
    # No constraint operator found — treat required as plain version
    return compare_versions(actual, required) >= 0


def generate_instance_id() -> str:
    """Generate a unique instance id using a random UUID4 hex string."""
    return uuid.uuid4().hex


def merge_configs(default: dict, override: dict) -> dict:
    """Deep merge two configuration dictionaries.

    Values in ``override`` take precedence over ``default``. Nested
    dictionaries are merged recursively; all other types in ``override``
    replace the corresponding value in ``default``.
    """
    result: Dict[Any, Any] = dict(default)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def truncate_text(text: str, max_len: int = 100) -> str:
    """Truncate text to ``max_len`` characters, appending an ellipsis.

    If ``max_len`` is too small to fit an ellipsis, the text is cut
    without one. ``None`` input is treated as an empty string.
    """
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def safe_import(module_path: str) -> Optional[ModuleType]:
    """Safely import a module by its dotted path.

    Returns the imported module on success, or ``None`` if the module
    cannot be imported.
    """
    try:
        return importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError):
        return None
