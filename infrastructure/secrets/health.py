"""
Secrets platform health check.

Provides unified health monitoring for
the secrets platform components,
including provider connectivity,
cache status, resolver availability,
and audit system health.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class SecretsHealthCheck:
    """
    Secrets platform health checker.

    Performs comprehensive health checks
    on all secrets platform components,
    providing a single health status
    for monitoring and alerting.

    Usage:
        health = SecretsHealthCheck(manager=manager)
        status = await health.check_all()
        if not status["healthy"]:
            print("Platform unhealthy!")
    """

    def __init__(
        self,
        manager: Optional[Any] = None,
        provider: Optional[Any] = None,
        cache: Optional[Any] = None,
        resolver: Optional[Any] = None,
        registry: Optional[Any] = None,
        audit: Optional[Any] = None,
    ) -> None:
        """
        Initialize health checker.

        Args:
            manager: SecretsManager instance.
            provider: SecretsProvider instance.
            cache: SecretsCache instance.
            resolver: SecretResolver instance.
            registry: SecretsRegistry instance.
            audit: SecretsAudit instance.
        """
        self._manager = manager
        self._provider = provider
        self._cache = cache
        self._resolver = resolver
        self._registry = registry
        self._audit = audit
        self._custom_checks: List[Dict[str, Any]] = []

    def add_check(
        self,
        name: str,
        check_fn: Callable,
    ) -> None:
        """
        Add a custom health check.

        Args:
            name: Check name.
            check_fn: Async callable returning bool.
        """
        self._custom_checks.append({
            "name": name,
            "check_fn": check_fn,
        })

    async def check_all(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check.

        Returns:
            Health status dictionary.
        """
        results = {
            "healthy": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": await self._check_provider(),
            "cache": self._check_cache(),
            "resolver": self._check_resolver(),
            "registry": self._check_registry(),
            "audit": self._check_audit(),
        }

        # Run custom checks
        for custom in self._custom_checks:
            try:
                result = await custom["check_fn"]()
                results[custom["name"]] = bool(result)
                if not result:
                    results["healthy"] = False
            except Exception:
                results[custom["name"]] = False
                results["healthy"] = False

        # Determine overall health
        component_checks = [
            results["provider"],
            results["cache"],
            results["resolver"],
            results["registry"],
            results["audit"],
        ]
        results["healthy"] = all(component_checks) and all(
            v is True or v is None for v in component_checks
        )

        return results

    async def _check_provider(self) -> Optional[bool]:
        """Check provider health."""
        if self._manager:
            try:
                health = await self._manager.health_check()
                return health.get("provider", True)
            except Exception:
                return False

        if self._provider:
            try:
                health = await self._provider.health_check()
                return health.get("healthy", True)
            except Exception:
                return False

        return None

    def _check_cache(self) -> Optional[bool]:
        """Check cache health."""
        if self._cache:
            try:
                stats = self._cache.get_stats()
                return stats.get("entries", 0) >= 0
            except Exception:
                return False
        return None

    def _check_resolver(self) -> Optional[bool]:
        """Check resolver health."""
        if self._resolver:
            try:
                stats = self._resolver.get_stats()
                return "total_resolutions" in stats
            except Exception:
                return False
        return None

    def _check_registry(self) -> Optional[bool]:
        """Check registry health."""
        if self._registry:
            try:
                self._registry.total_count()
                return True
            except Exception:
                return False
        return None

    def _check_audit(self) -> Optional[bool]:
        """Check audit system health."""
        if self._audit:
            try:
                stats = self._audit.get_stats()
                return "enabled" in stats
            except Exception:
                return False
        return None

    def get_quick_status(self) -> Dict[str, Any]:
        """
        Get a quick health status without full checks.

        Returns:
            Quick status dictionary.
        """
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider_configured": self._provider is not None or self._manager is not None,
            "cache_configured": self._cache is not None,
            "resolver_configured": self._resolver is not None,
            "registry_configured": self._registry is not None,
            "audit_configured": self._audit is not None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get health check statistics."""
        return {
            "components": {
                "manager": self._manager is not None,
                "provider": self._provider is not None,
                "cache": self._cache is not None,
                "resolver": self._resolver is not None,
                "registry": self._registry is not None,
                "audit": self._audit is not None,
            },
            "custom_checks": len(self._custom_checks),
        }
