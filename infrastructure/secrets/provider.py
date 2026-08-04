"""
Secrets provider framework.

Defines the abstract base class for
all secrets providers, enabling
pluggable backends for vault, cloud
providers, and local storage.
"""

from __future__ import annotations

import abc
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import SecretsProvider as SecretsProviderType
from .exceptions import SecretNotFoundError, SecretProviderError
from .models import SecretItem

logger = logging.getLogger(__name__)


class SecretsProvider(abc.ABC):
    """
    Abstract secrets provider.

    All secrets backends must implement
    this interface to provide consistent
    read/write/list/delete operations.

    Usage:
        class VaultProvider(SecretsProvider):
            async def read(self, key, namespace):
                ...
    """

    name: str = "base"

    async def read(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretItem]:
        """
        Read a secret by key.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            SecretItem or None.
        """
        ...

    async def write(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        """
        Write a secret value.

        Args:
            key: The secret key.
            value: The secret value.
            namespace: Namespace.
            **kwargs: Additional metadata.

        Returns:
            Created SecretItem.
        """
        ...

    async def update(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        """
        Update an existing secret.

        Args:
            key: The secret key.
            value: New value.
            namespace: Namespace.
            **kwargs: Additional metadata.

        Returns:
            Updated SecretItem.
        """
        ...

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Delete a secret.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            True if deleted.
        """
        ...

    async def list(
        self,
        namespace: str = "default",
    ) -> List[str]:
        """
        List all secret keys.

        Args:
            namespace: Namespace.

        Returns:
            List of secret keys.
        """
        ...

    async def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Check if a secret exists.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            True if exists.
        """
        ...

    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider health.

        Returns:
            Health status dict.
        """
        ...


class LocalSecretsProvider(SecretsProvider):
    """
    Local in-memory secrets provider.

    Stores secrets in memory for development
    and testing purposes. Not suitable for
    production use.

    Usage:
        provider = LocalSecretsProvider()
        await provider.write("db/password", "secret123")
        item = await provider.read("db/password")
    """

    name = "local"

    def __init__(self) -> None:
        self._storage: Dict[str, Dict[str, SecretItem]] = {}
        self._lock = asyncio.Lock()
        self._healthy = True

    async def read(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretItem]:
        async with self._lock:
            ns_secrets = self._storage.get(namespace, {})
            return ns_secrets.get(key)

    async def write(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        async with self._lock:
            if namespace not in self._storage:
                self._storage[namespace] = {}

            existing = self._storage[namespace].get(key)
            version = (existing.version + 1) if existing else 1

            item = SecretItem(
                key=key,
                value=value,
                provider=self.name,
                version=version,
                created_at=datetime.utcnow(),
                expires_at=kwargs.get("expires_at"),
                readonly=kwargs.get("readonly", False),
                category=kwargs.get("category"),
                format=kwargs.get("format"),
                namespace=namespace,
                metadata=kwargs.get("metadata", {}),
            )

            self._storage[namespace][key] = item
            return item

    async def update(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        async with self._lock:
            if namespace not in self._storage or key not in self._storage[namespace]:
                raise SecretNotFoundError(key, namespace)

            existing = self._storage[namespace][key]
            version = existing.version + 1

            item = SecretItem(
                key=key,
                value=value,
                provider=self.name,
                version=version,
                created_at=datetime.utcnow(),
                expires_at=kwargs.get("expires_at", existing.expires_at),
                readonly=kwargs.get("readonly", existing.readonly),
                category=kwargs.get("category", existing.category),
                format=kwargs.get("format", existing.format),
                namespace=namespace,
                metadata=kwargs.get("metadata", existing.metadata),
            )

            self._storage[namespace][key] = item
            return item

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        async with self._lock:
            if namespace not in self._storage or key not in self._storage[namespace]:
                return False
            del self._storage[namespace][key]
            return True

    async def list(
        self,
        namespace: str = "default",
    ) -> List[str]:
        async with self._lock:
            return list(self._storage.get(namespace, {}).keys())

    async def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        async with self._lock:
            return key in self._storage.get(namespace, {})

    async def health_check(self) -> Dict[str, Any]:
        async with self._lock:
            total = sum(len(secrets) for secrets in self._storage.values())
            return {
                "healthy": self._healthy,
                "provider": self.name,
                "total_secrets": total,
                "namespaces": list(self._storage.keys()),
            }


class EnvironmentSecretsProvider(SecretsProvider):
    """
    Environment variable secrets provider.

    Reads secrets from environment variables,
    using the secret key as the environment
    variable name (with path separators replaced
    by underscores).

    Usage:
        provider = EnvironmentSecretsProvider()
        item = await provider.read("DB_PASSWORD")
    """

    name = "environment"

    def __init__(self) -> None:
        self._env_vars: Dict[str, str] = {}
        self._readonly = True

    async def read(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretItem]:
        import os

        env_key = key.replace("/", "_").replace("-", "_").upper()
        value = os.environ.get(env_key)

        if value is None:
            value = self._env_vars.get(f"{namespace}/{key}")

        if value is None:
            return None

        return SecretItem(
            key=key,
            value=value,
            provider=self.name,
            version=1,
            created_at=datetime.utcnow(),
            readonly=self._readonly,
            namespace=namespace,
        )

    async def write(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        # Environment provider is read-only
        self._env_vars[f"{namespace}/{key}"] = value
        return SecretItem(
            key=key,
            value=value,
            provider=self.name,
            version=1,
            created_at=datetime.utcnow(),
            readonly=True,
            namespace=namespace,
        )

    async def update(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        # Environment provider is read-only
        self._env_vars[f"{namespace}/{key}"] = value
        return SecretItem(
            key=key,
            value=value,
            provider=self.name,
            version=2,
            created_at=datetime.utcnow(),
            readonly=True,
            namespace=namespace,
        )

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        self._env_vars.pop(f"{namespace}/{key}", None)
        return True

    async def list(
        self,
        namespace: str = "default",
    ) -> List[str]:
        return [
            key.split("/", 1)[1]
            for key in self._env_vars
            if key.startswith(f"{namespace}/")
        ]

    async def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        import os

        env_key = key.replace("/", "_").replace("-", "_").upper()
        return env_key in os.environ or f"{namespace}/{key}" in self._env_vars

    async def health_check(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "provider": self.name,
            "type": "read_only",
        }


class ProviderFactory:
    """
    Factory for creating secrets providers.

    Manages provider registration and
    instantiation, supporting custom
    provider registration.

    Usage:
        factory = ProviderFactory()
        factory.register("vault", VaultProvider)
        provider = factory.create("vault")
    """

    def __init__(self) -> None:
        self._providers: Dict[str, type] = {
            SecretsProviderType.LOCAL.value: LocalSecretsProvider,
            SecretsProviderType.ENVIRONMENT.value: EnvironmentSecretsProvider,
        }

    def register(
        self,
        name: str,
        provider_class: type,
    ) -> None:
        """
        Register a provider class.

        Args:
            name: Provider name.
            provider_class: Provider class.
        """
        self._providers[name] = provider_class

    def create(
        self,
        name: str,
        **kwargs: Any,
    ) -> SecretsProvider:
        """
        Create a provider instance.

        Args:
            name: Provider name.
            **kwargs: Provider constructor args.

        Returns:
            Provider instance.

        Raises:
            SecretProviderError: If provider not found.
        """
        if name not in self._providers:
            available = list(self._providers.keys())
            raise SecretProviderError(
                name, "create", f"Unknown provider. Available: {available}"
            )

        provider_class = self._providers[name]
        return provider_class(**kwargs)

    def list_providers(self) -> List[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._providers
