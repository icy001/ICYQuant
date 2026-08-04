"""
Configuration utilities.

Helper functions for common configuration
operations, including key manipulation,
value conversion, and deep merging.
"""

from __future__ import annotations

from typing import Any, Dict, List


def deep_merge(
    base: Dict[str, Any],
    override: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Values from 'override' take precedence.
    Nested dictionaries are merged recursively.

    Args:
        base: Base dictionary.
        override: Dictionary with override values.

    Returns:
        Merged dictionary.
    """

    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(
    data: Dict[str, Any],
    prefix: str = "",
    separator: str = ".",
) -> Dict[str, Any]:
    """
    Flatten a nested dictionary.

    Example:
        {"server": {"port": 8080}}
        -> {"server.port": 8080}

    Args:
        data: Nested dictionary.
        prefix: Key prefix.
        separator: Key separator.

    Returns:
        Flattened dictionary.
    """

    items: Dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}{separator}{key}" if prefix else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, full_key, separator))
        else:
            items[full_key] = value
    return items


def unflatten_dict(
    data: Dict[str, Any],
    separator: str = ".",
) -> Dict[str, Any]:
    """
    Unflatten a dictionary with separator keys.

    Example:
        {"server.port": 8080}
        -> {"server": {"port": 8080}}

    Args:
        data: Flattened dictionary.
        separator: Key separator.

    Returns:
        Nested dictionary.
    """

    result: Dict[str, Any] = {}
    for key, value in data.items():
        parts = key.split(separator)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def parse_value(
    value: str,
) -> Any:
    """
    Parse a string value to appropriate type.

    Attempts to parse as:
    1. JSON (handles numbers, booleans, null, lists, dicts)
    2. Falls back to string

    Args:
        value: String value to parse.

    Returns:
        Parsed value.
    """

    import json

    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


def get_nested(
    data: Dict[str, Any],
    key: str,
    default: Any = None,
    separator: str = ".",
) -> Any:
    """
    Get a nested value by dotted key.

    Example:
        get_nested({"server": {"port": 8080}}, "server.port")
        -> 8080

    Args:
        data: Dictionary to search.
        key: Dotted key (e.g., "server.port").
        default: Default value if not found.
        separator: Key separator.

    Returns:
        Value or default.
    """

    parts = key.split(separator)
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def set_nested(
    data: Dict[str, Any],
    key: str,
    value: Any,
    separator: str = ".",
) -> None:
    """
    Set a nested value by dotted key.

    Args:
        data: Dictionary to modify.
        key: Dotted key.
        value: Value to set.
        separator: Key separator.
    """

    parts = key.split(separator)
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def mask_sensitive(
    value: Any,
    key: str = "",
    sensitive_keys: list | None = None,
) -> Any:
    """
    Mask sensitive values for logging.

    Args:
        value: Value to mask.
        key: Configuration key (for detecting sensitive keys).
        sensitive_keys: List of sensitive key patterns.

    Returns:
        Masked value if sensitive, otherwise original.
    """

    if sensitive_keys is None:
        sensitive_keys = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "private_key",
            "credential",
        ]

    if not isinstance(value, str):
        return value

    key_lower = key.lower()
    is_sensitive = any(
        pattern in key_lower for pattern in sensitive_keys
    )

    if is_sensitive:
        if len(value) <= 4:
            return "****"
        return value[:2] + "****" + value[-2:]

    return value
