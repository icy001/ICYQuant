"""
Secret resolution engine.

Provides the ${secret:...} reference
resolution system, enabling automatic
secret resolution within configuration
values and other strings.

Supports provider-based routing:
- ${secret:key} -> default provider
- ${secret:vault/key} -> vault provider
- ${secret:local/key} -> local provider
"""

from __future__ import annotations

import re
import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import SECRET_PATTERN
from .exceptions import SecretResolutionError
from .utils import is_secret_reference, parse_secret_reference

# Provider prefix routing
PROVIDER_PREFIX_MAP: Dict[str, str] = {
    "vault": "vault",
    "local": "local",
    "environment": "environment",
    "aws": "aws_secrets_manager",
    "azure": "azure_key_vault",
    "gcp": "google_secret_manager",
}


class SecretResolver:
    """
    Secret reference resolver.

    Resolves ${secret:key/path} references
    in strings by looking up secrets from
    a provider or registry, supporting
    both synchronous and asynchronous
    resolution modes.

    Supports provider prefix routing:
    ${secret:vault/database/password} routes
    to the vault provider automatically.

    Usage:
        resolver = SecretResolver(provider=my_provider)
        value = await resolver.resolve("${secret:db/password}")
        # With provider router:
        resolver.set_provider_router(router_fn)
    """

    def __init__(
        self,
        provider: Any = None,
        registry: Any = None,
        cache: Any = None,
    ) -> None:
        """
        Initialize resolver.

        Args:
            provider: Secrets provider for lookups.
            registry: Secrets registry for lookups.
            cache: Secrets cache for lookups.
        """
        self._provider = provider
        self._registry = registry
        self._cache = cache
        self._resolve_count = 0
        self._fail_count = 0
        self._provider_router: Optional[Callable[[str], Any]] = None
        self._provider_stats: Dict[str, int] = {}

    def set_provider(self, provider: Any) -> None:
        """Set the secrets provider."""
        self._provider = provider

    def set_registry(self, registry: Any) -> None:
        """Set the secrets registry."""
        self._registry = registry

    def set_cache(self, cache: Any) -> None:
        """Set the secrets cache."""
        self._cache = cache

    def set_provider_router(
        self,
        router: Callable[[str], Any],
    ) -> None:
        """
        Set a provider router function.

        The router maps a provider name to a
        provider instance for routing
        ${secret:provider/key} references.

        Args:
            router: Callable(provider_name) -> provider_instance
        """
        self._provider_router = router

    def _parse_provider_prefix(
        self,
        key: str,
    ) -> Tuple[str, str]:
        """
        Parse provider prefix from key.

        Args:
            key: Secret key path.

        Returns:
            Tuple of (provider_name, actual_key).
        """
        if "/" in key:
            prefix, rest = key.split("/", 1)
            if prefix in PROVIDER_PREFIX_MAP:
                return PROVIDER_PREFIX_MAP[prefix], rest
        return "default", key

    def _get_provider_for_key(
        self,
        key: str,
    ) -> Tuple[Any, str]:
        """
        Get the appropriate provider for a key.

        Args:
            key: Secret key path.

        Returns:
            Tuple of (provider, actual_key).
        """
        provider_name, actual_key = self._parse_provider_prefix(key)

        if provider_name == "default":
            return self._provider, actual_key

        if self._provider_router:
            provider = self._provider_router(provider_name)
            if provider:
                return provider, actual_key

        # Fall back to default provider
        return self._provider, actual_key

    # ── Sync Resolution ──

    def resolve(
        self,
        reference: str,
    ) -> Optional[str]:
        """
        Resolve a ${secret:...} reference (sync).

        Supports provider prefix routing:
        ${secret:vault/key} routes to vault provider.

        Args:
            reference: The reference string.

        Returns:
            Resolved secret value or None.
        """
        parsed = parse_secret_reference(reference)
        if not parsed:
            raise SecretResolutionError(reference, "Invalid reference format")

        key = parsed["key"]
        namespace = parsed.get("namespace", "default")

        # Get provider and actual key
        provider, actual_key = self._get_provider_for_key(key)

        # Track provider usage
        self._provider_stats[
            getattr(provider, "name", "unknown")
        ] = self._provider_stats.get(
            getattr(provider, "name", "unknown"), 0
        ) + 1

        # Try cache first (with actual_key)
        if self._cache:
            cached = self._cache.get(actual_key, namespace)
            if cached is not None:
                self._resolve_count += 1
                return cached

        # Try provider
        if provider:
            try:
                item = provider.read(actual_key, namespace)
                if item and hasattr(item, "value"):
                    if self._cache:
                        self._cache.put(actual_key, item.value, namespace)
                    self._resolve_count += 1
                    return item.value
                elif isinstance(item, str):
                    if self._cache:
                        self._cache.put(actual_key, item, namespace)
                    self._resolve_count += 1
                    return item
            except Exception:
                pass

        # Try registry
        if self._registry:
            try:
                item = self._registry.get(actual_key, namespace)
                if self._cache:
                    self._cache.put(actual_key, item.value, namespace)
                self._resolve_count += 1
                return item.value
            except Exception:
                pass

        self._fail_count += 1
        return None

    def resolve_in_text(
        self,
        text: str,
    ) -> str:
        """
        Resolve all ${secret:...} references in text (sync).

        Args:
            text: Text containing references.

        Returns:
            Text with all references resolved.
        """
        def _replace(match: re.Match) -> str:
            reference = match.group(0)
            parsed = parse_secret_reference(reference)
            if not parsed:
                return reference

            key = parsed["key"]
            namespace = parsed.get("namespace", "default")

            # Get provider and actual key via routing
            provider, actual_key = self._get_provider_for_key(key)

            # Try cache first
            if self._cache:
                cached = self._cache.get(actual_key, namespace)
                if cached is not None:
                    return cached

            # Try provider
            if provider:
                try:
                    item = provider.read(actual_key, namespace)
                    if item and hasattr(item, "value"):
                        if self._cache:
                            self._cache.put(actual_key, item.value, namespace)
                        return item.value
                    elif isinstance(item, str):
                        if self._cache:
                            self._cache.put(actual_key, item, namespace)
                        return item
                except Exception:
                    pass

            # Try registry
            if self._registry:
                try:
                    item = self._registry.get(actual_key, namespace)
                    if self._cache:
                        self._cache.put(actual_key, item.value, namespace)
                    return item.value
                except Exception:
                    pass

            return reference

        return re.sub(SECRET_PATTERN, _replace, text)

    # ── Async Resolution ──

    async def async_resolve(
        self,
        reference: str,
    ) -> Optional[str]:
        """
        Resolve a ${secret:...} reference (async).

        Args:
            reference: The reference string.

        Returns:
            Resolved secret value or None.
        """
        parsed = parse_secret_reference(reference)
        if not parsed:
            raise SecretResolutionError(reference, "Invalid reference format")

        key = parsed["key"]
        namespace = parsed.get("namespace", "default")

        # Try cache
        if self._cache:
            cached = await self._cache.async_get(key, namespace)
            if cached is not None:
                self._resolve_count += 1
                return cached

        # Try provider
        if self._provider:
            try:
                item = await self._provider.read(key, namespace)
                if item:
                    # Cache the value
                    if self._cache:
                        await self._cache.async_put(key, item.value, namespace)
                    self._resolve_count += 1
                    return item.value
            except Exception:
                pass

        # Try registry
        if self._registry:
            try:
                item = self._registry.get(key, namespace)
                if item:
                    if self._cache:
                        await self._cache.async_put(key, item.value, namespace)
                    self._resolve_count += 1
                    return item.value
            except Exception:
                pass

        self._fail_count += 1
        return None

    async def async_resolve_in_text(
        self,
        text: str,
    ) -> str:
        """
        Resolve all ${secret:...} references in text (async).

        Args:
            text: Text containing references.

        Returns:
            Text with all references resolved.
        """
        references = self._find_references(text)
        if not references:
            return text

        resolved = {}
        for ref in references:
            value = await self.async_resolve(ref)
            resolved[ref] = value if value is not None else ref

        result = text
        for ref, value in resolved.items():
            result = result.replace(ref, value)

        return result

    # ── Batch Resolution ──

    async def async_resolve_batch(
        self,
        references: List[str],
    ) -> Dict[str, Optional[str]]:
        """
        Resolve multiple references in batch.

        Args:
            references: List of reference strings.

        Returns:
            Dict mapping reference to resolved value.
        """
        results: Dict[str, Optional[str]] = {}
        seen = set()

        for ref in references:
            if ref in seen:
                continue
            seen.add(ref)

            try:
                result = await self.async_resolve(ref)
                results[ref] = result
            except Exception:
                results[ref] = None

        return results

    def resolve_batch(
        self,
        references: List[str],
    ) -> Dict[str, Optional[str]]:
        """
        Resolve multiple references (sync).

        Args:
            references: List of reference strings.

        Returns:
            Dict mapping reference to resolved value.
        """
        results: Dict[str, Optional[str]] = {}
        seen = set()

        for ref in references:
            if ref in seen:
                continue
            seen.add(ref)

            try:
                result = self.resolve(ref)
                results[ref] = result
            except Exception:
                results[ref] = None

        return results

    # ── Utility ──

    def extract_references(
        self,
        text: str,
    ) -> List[str]:
        """
        Extract all ${secret:...} references from text.

        Args:
            text: Text to scan.

        Returns:
            List of reference strings.
        """
        return self._find_references(text)

    def has_references(
        self,
        text: str,
    ) -> bool:
        """Check if text contains any secret references."""
        return len(self._find_references(text)) > 0

    def _find_references(
        self,
        text: str,
    ) -> List[str]:
        """Find all ${secret:...} references in text."""
        if not text:
            return []
        # re.findall with groups returns captured groups only, so use finditer
        # to get full matches
        return [m.group(0) for m in re.finditer(SECRET_PATTERN, text)]

    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        total = self._resolve_count + self._fail_count
        success_rate = self._resolve_count / total if total > 0 else 0.0
        return {
            "total_resolutions": total,
            "successful": self._resolve_count,
            "failed": self._fail_count,
            "success_rate": round(success_rate, 4),
            "provider_usage": dict(self._provider_stats),
        }
