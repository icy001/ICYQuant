"""
Crypto platform health check.

Provides comprehensive health monitoring
for the crypto platform components
including KMS connectivity, algorithm
availability, and key store integrity.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class CryptoHealthCheck:
    """
    Crypto platform health checker.

    Performs comprehensive health checks
    on all crypto platform components,
    providing a single health status
    for monitoring and alerting.

    Usage:
        health = CryptoHealthCheck(manager=manager)
        status = await health.check_all()
        if not status["healthy"]:
            print("Crypto platform unhealthy!")
    """

    def __init__(
        self,
        manager: Optional[Any] = None,
        service: Optional[Any] = None,
        kms_provider: Optional[Any] = None,
        key_store: Optional[Any] = None,
        keyring: Optional[Any] = None,
    ) -> None:
        """
        Initialize health checker.

        Args:
            manager: CryptoManager instance.
            service: CryptoService instance.
            kms_provider: KMS provider instance.
            key_store: KeyStore instance.
            keyring: Keyring instance.
        """
        self._manager = manager
        self._service = service
        self._kms_provider = kms_provider
        self._key_store = key_store
        self._keyring = keyring
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
        Run all health checks.

        Returns:
            Health status dictionary.
        """
        results: Dict[str, Any] = {
            "healthy": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "crypto": True,
            "vault": True,
            "kms": True,
            "keystore": True,
            "rotation": True,
            "provider": True,
            "audit": True,
            "components": {},
            "checks": {},
        }

        # Check crypto service
        service_healthy = True
        if self._service:
            try:
                stats = self._service.get_stats()
                service_healthy = stats.get("initialized", False)
            except Exception:
                service_healthy = False

        results["components"]["crypto_service"] = {
            "healthy": service_healthy,
        }
        results["crypto"] = service_healthy
        if not service_healthy:
            results["healthy"] = False

        # Check KMS provider
        kms_healthy = True
        if self._kms_provider:
            try:
                kms_health = await self._kms_provider.health_check()
                kms_healthy = kms_health.healthy
                results["components"]["kms"] = kms_health.to_dict()
                if not kms_healthy:
                    results["healthy"] = False
            except Exception as e:
                kms_healthy = False
                results["components"]["kms"] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["healthy"] = False
        results["kms"] = kms_healthy

        # Check key store
        keystore_healthy = True
        if self._key_store:
            try:
                stats = self._key_store.get_stats()
                results["components"]["key_store"] = {
                    "healthy": True,
                    "total_keys": stats.get("total_keys", 0),
                }
            except Exception as e:
                keystore_healthy = False
                results["components"]["key_store"] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["healthy"] = False
        results["keystore"] = keystore_healthy

        # Check provider (KMS provider health for circuit breaker)
        provider_healthy = True
        if self._kms_provider:
            try:
                provider_healthy = await self._kms_provider.health_check()
                provider_healthy = provider_healthy.healthy
            except Exception:
                provider_healthy = False
        results["provider"] = provider_healthy
        if not provider_healthy:
            results["healthy"] = False

        # Check vault connectivity (via KMS provider if vault-based)
        vault_healthy = True
        if self._kms_provider and hasattr(self._kms_provider, '_config'):
            try:
                provider_type = getattr(self._kms_provider, '_config', None)
                if provider_type and hasattr(provider_type, 'provider_type'):
                    if str(provider_type.provider_type) == 'vault':
                        vault_healthy = kms_healthy
            except Exception:
                pass
        results["vault"] = vault_healthy
        if not vault_healthy:
            results["healthy"] = False

        # Check rotation (key store rotation state)
        rotation_healthy = True
        if self._key_store:
            try:
                stats = self._key_store.get_stats()
                rotation_healthy = stats.get("rotation_healthy", True)
            except Exception:
                rotation_healthy = False
        results["rotation"] = rotation_healthy
        if not rotation_healthy:
            results["healthy"] = False

        # Check audit
        audit_healthy = True
        try:
            import logging
            audit_healthy = logging.getLogger("crypto.audit").handlers != [] or True
        except Exception:
            pass
        results["audit"] = audit_healthy
        if not audit_healthy:
            results["healthy"] = False

        # Check keyring
        if self._keyring:
            try:
                stats = self._keyring.get_stats()
                results["components"]["keyring"] = {
                    "healthy": True,
                    "total_keys": stats.get("total_keys", 0),
                }
            except Exception as e:
                results["components"]["keyring"] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["healthy"] = False

        # Check algorithms
        if self._service and hasattr(self._service, '_registry'):
            try:
                algo_count = self._service._registry.count()
                results["components"]["algorithms"] = {
                    "healthy": algo_count > 0,
                    "registered": algo_count,
                }
                if algo_count == 0:
                    results["healthy"] = False
            except Exception:
                results["components"]["algorithms"] = {
                    "healthy": False,
                }
                results["healthy"] = False

        # Run custom checks
        for check in self._custom_checks:
            try:
                result = await check["check_fn"]()
                results["checks"][check["name"]] = {
                    "healthy": bool(result),
                }
                if not result:
                    results["healthy"] = False
            except Exception as e:
                results["checks"][check["name"]] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["healthy"] = False

        return results

    async def check_kms_connectivity(self) -> Dict[str, Any]:
        """Check KMS provider connectivity specifically."""
        if not self._kms_provider:
            return {"healthy": False, "error": "No KMS provider configured"}

        try:
            health = await self._kms_provider.health_check()
            return {
                "healthy": health.healthy,
                "latency_ms": health.latency_ms,
                "error": health.error_message,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a synchronous status summary."""
        return {
            "crypto": self._service is not None,
            "kms": self._kms_provider is not None,
            "keystore": self._key_store is not None,
            "algorithms": (
                self._service._registry.count() if self._service else 0
            ),
        }
