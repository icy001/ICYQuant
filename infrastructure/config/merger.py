"""
Configuration Merger.

Merges multiple configuration sources into a single
unified configuration dictionary.

Supports multiple merge strategies:
- Flat Merge: Simple key-value override
- Recursive Merge: Deep nested dictionary merging
- List Replace: Replace list values entirely
- List Append: Append list values
- Deep Merge: Full recursive merge with list handling
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .priority import MergeStrategy


class ConfigurationMerger:
    """
    Merges configuration dictionaries.

    Supports multiple strategies for how values
    from different sources are combined.

    Usage:
        merger = ConfigurationMerger(strategy="recursive")
        result = merger.merge(configs)
    """

    def __init__(
        self,
        strategy: str = MergeStrategy.RECURSIVE,
    ) -> None:
        """
        Initialize merger with a merge strategy.

        Args:
            strategy: Merge strategy name.
        """
        self._strategy = strategy

    @property
    def strategy(
        self,
    ) -> str:
        """Get current strategy."""
        return self._strategy

    def set_strategy(
        self,
        strategy: str,
    ) -> None:
        """Set merge strategy."""
        self._strategy = strategy

    def merge(
        self,
        configs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.

        Configs should be ordered by priority (lowest first),
        so higher priority configs override lower ones.

        Args:
            configs: List of configuration dictionaries.

        Returns:
            Merged configuration dictionary.
        """
        result: Dict[str, Any] = {}

        for config in configs:
            if config is None:
                continue
            result = self._merge_two(result, config)

        return result

    def _merge_two(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge two dictionaries using the current strategy."""

        strategy = self._strategy

        if strategy == MergeStrategy.FLAT:
            return self._flat_merge(base, override)
        elif strategy == MergeStrategy.RECURSIVE:
            return self._recursive_merge(base, override)
        elif strategy == MergeStrategy.DEEP:
            return self._deep_merge(base, override)
        elif strategy == MergeStrategy.LIST_REPLACE:
            return self._list_replace_merge(base, override)
        elif strategy == MergeStrategy.LIST_APPEND:
            return self._list_append_merge(base, override)
        else:
            # Default to recursive
            return self._recursive_merge(base, override)

    def _flat_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Simple flat merge (override wins)."""
        result = dict(base)
        result.update(override)
        return result

    def _recursive_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursive merge (dicts merged, other values overridden)."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._recursive_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _deep_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deep merge (dicts merged, lists appended)."""
        result = dict(base)
        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    result[key] = result[key] + value
                else:
                    result[key] = value
            else:
                result[key] = value
        return result

    def _list_replace_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge with list replacement (override lists completely)."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._list_replace_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _list_append_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge with list append (append lists instead of replacing)."""
        result = dict(base)
        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._list_append_merge(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    result[key] = result[key] + value
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
