"""
Feature flag platform registry.

Provides a thread-safe registry for managing
feature flag definitions with registration,
unregistration, tagging, and bulk operations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from .constants import FlagStatus
from .exceptions import (
    FeatureFlagAlreadyExistsError,
    FeatureFlagNotFoundError,
)
from .models import FeatureFlag

logger = logging.getLogger(__name__)


class FeatureRegistry:
    """
    Thread-safe registry for feature flag definitions.

    Stores and manages feature flag definitions with
    support for registration, unregistration, tagging,
    filtering, and bulk operations. Notifies listeners
    on flag changes for cache invalidation.

    Usage:
        registry = FeatureRegistry()
        await registry.register(my_flag)
        flag = registry.get("my.feature.key")
        active = registry.list_active()
    """

    def __init__(self) -> None:
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()
        self._listeners: List[Any] = []
        self._version_counter = 0

    async def register(
        self,
        flag: FeatureFlag,
        force: bool = False,
    ) -> FeatureFlag:
        """
        Register a feature flag.

        Args:
            flag: Feature flag to register.
            force: If True, overwrite existing flag.

        Returns:
            The registered feature flag.

        Raises:
            FeatureFlagAlreadyExistsError: If flag already
                exists and force is False.
        """
        async with self._lock:
            if flag.key in self._flags and not force:
                raise FeatureFlagAlreadyExistsError(flag.key)

            self._flags[flag.key] = flag
            self._version_counter += 1

            logger.info(
                "Registered feature flag: %s (enabled=%s, type=%s)",
                flag.key, flag.enabled, flag.flag_type.value,
            )

            self._notify_listeners("register", flag)
            return flag

    async def unregister(
        self,
        key: str,
    ) -> bool:
        """
        Unregister a feature flag.

        Args:
            key: Feature flag key to remove.

        Returns:
            True if the flag was removed.

        Raises:
            FeatureFlagNotFoundError: If flag not found.
        """
        async with self._lock:
            if key not in self._flags:
                raise FeatureFlagNotFoundError(key)

            flag = self._flags.pop(key)
            self._version_counter += 1

            logger.info("Unregistered feature flag: %s", key)
            self._notify_listeners("unregister", flag)
            return True

    def get(
        self,
        key: str,
    ) -> Optional[FeatureFlag]:
        """
        Get a feature flag by key.

        Args:
            key: Feature flag key.

        Returns:
            FeatureFlag or None if not found.
        """
        return self._flags.get(key)

    async def get_all(self) -> Dict[str, FeatureFlag]:
        """
        Get all registered feature flags.

        Returns:
            Dictionary of all flags.
        """
        async with self._lock:
            return dict(self._flags)

    def list_active(
        self,
    ) -> List[FeatureFlag]:
        """
        List all active feature flags.

        Returns:
            List of active flags.
        """
        return [
            f for f in self._flags.values()
            if f.status == FlagStatus.ACTIVE and f.enabled
        ]

    def list_by_tag(
        self,
        tag: str,
    ) -> List[FeatureFlag]:
        """
        List feature flags filtered by tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of matching flags.
        """
        return [f for f in self._flags.values() if tag in f.tags]

    def list_by_status(
        self,
        status: FlagStatus,
    ) -> List[FeatureFlag]:
        """
        List feature flags by status.

        Args:
            status: Flag status to filter by.

        Returns:
            List of matching flags.
        """
        return [f for f in self._flags.values() if f.status == status]

    def list_keys(
        self,
    ) -> List[str]:
        """Get all registered flag keys."""
        return list(self._flags.keys())

    def count(self) -> int:
        """Get total number of registered flags."""
        return len(self._flags)

    def count_by_status(self) -> Dict[str, int]:
        """Count flags by status."""
        counts: Dict[str, int] = {}
        for status in FlagStatus:
            counts[status.value] = 0
        for flag in self._flags.values():
            counts[flag.status.value] = counts.get(flag.status.value, 0) + 1
        return counts

    async def enable(
        self,
        key: str,
    ) -> FeatureFlag:
        """
        Enable a feature flag.

        Args:
            key: Flag key to enable.

        Returns:
            Updated FeatureFlag.

        Raises:
            FeatureFlagNotFoundError: If flag not found.
        """
        async with self._lock:
            flag = self._flags.get(key)
            if flag is None:
                raise FeatureFlagNotFoundError(key)

            updated = FeatureFlag(
                key=flag.key,
                enabled=True,
                description=flag.description,
                flag_type=flag.flag_type,
                strategy=flag.strategy,
                default_value=flag.default_value,
                tags=flag.tags,
                metadata=flag.metadata,
                rules=flag.rules,
                status=FlagStatus.ACTIVE,
                created_at=flag.created_at,
                updated_at=datetime.utcnow(),
                owner=flag.owner,
                expires_at=flag.expires_at,
            )
            self._flags[key] = updated
            self._version_counter += 1
            self._notify_listeners("enable", updated)
            return updated

    async def disable(
        self,
        key: str,
    ) -> FeatureFlag:
        """
        Disable a feature flag.

        Args:
            key: Flag key to disable.

        Returns:
            Updated FeatureFlag.

        Raises:
            FeatureFlagNotFoundError: If flag not found.
        """
        async with self._lock:
            flag = self._flags.get(key)
            if flag is None:
                raise FeatureFlagNotFoundError(key)

            updated = FeatureFlag(
                key=flag.key,
                enabled=False,
                description=flag.description,
                flag_type=flag.flag_type,
                strategy=flag.strategy,
                default_value=flag.default_value,
                tags=flag.tags,
                metadata=flag.metadata,
                rules=flag.rules,
                status=FlagStatus.INACTIVE,
                created_at=flag.created_at,
                updated_at=datetime.utcnow(),
                owner=flag.owner,
                expires_at=flag.expires_at,
            )
            self._flags[key] = updated
            self._version_counter += 1
            self._notify_listeners("disable", updated)
            return updated

    async def bulk_register(
        self,
        flags: List[FeatureFlag],
        force: bool = False,
    ) -> Dict[str, bool]:
        """
        Register multiple feature flags.

        Args:
            flags: List of feature flags to register.
            force: Overwrite existing flags.

        Returns:
            Dictionary mapping keys to success status.
        """
        results: Dict[str, bool] = {}
        for flag in flags:
            try:
                await self.register(flag, force=force)
                results[flag.key] = True
            except Exception:
                results[flag.key] = False
        return results

    async def bulk_delete(
        self,
        keys: List[str],
    ) -> Dict[str, bool]:
        """
        Delete multiple feature flags.

        Args:
            keys: List of flag keys to delete.

        Returns:
            Dictionary mapping keys to success status.
        """
        results: Dict[str, bool] = {}
        for key in keys:
            try:
                await self.unregister(key)
                results[key] = True
            except Exception:
                results[key] = False
        return results

    def register_listener(
        self,
        listener: Any,
    ) -> None:
        """
        Register a change listener.

        Listener is called with (action, flag) on
        any registry change.

        Args:
            listener: Callable to register.
        """
        self._listeners.append(listener)

    def unregister_listener(
        self,
        listener: Any,
    ) -> None:
        """
        Unregister a change listener.

        Args:
            listener: Callable to remove.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_version(self) -> int:
        """Get the current registry version counter."""
        return self._version_counter

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_flags": len(self._flags),
            "active_flags": len(self.list_active()),
            "by_status": self.count_by_status(),
            "version": self._version_counter,
            "listeners": len(self._listeners),
        }

    async def clear(self) -> None:
        """Remove all registered flags."""
        async with self._lock:
            self._flags.clear()
            self._version_counter += 1
            logger.info("Cleared all feature flags from registry")

    def _notify_listeners(
        self,
        action: str,
        flag: FeatureFlag,
    ) -> None:
        """Notify all listeners of a change."""
        for listener in self._listeners:
            try:
                listener(action, flag)
            except Exception as e:
                logger.warning(
                    "Listener error for %s on %s: %s",
                    action, flag.key, e,
                )