"""Publisher registry for the plugin marketplace.

Provides :class:`MarketplaceRegistry` for managing publishers
and their packages, including verification and search capabilities.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketplaceRegistry:
    """Registry for plugin publishers and their packages.

    Maps ``publisher_id`` to publisher information including
    name, public key, package list, and verification status.

    Usage::

        reg = MarketplaceRegistry()
        reg.register_publisher("acme", "Acme Corp", public_key)
        reg.add_package("acme", {"id": "my.plugin", "version": "1.0"})
        results = reg.search_packages("momentum")
    """

    def __init__(self) -> None:
        self._publishers: Dict[str, Dict[str, Any]] = {}
        self._package_index: Dict[str, str] = {}
        self._register_count: int = 0
        self._verify_count: int = 0

    def register_publisher(
        self,
        publisher_id: str,
        name: str,
        public_key: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a new publisher.

        Args:
            publisher_id: Unique publisher identifier.
            name: Publisher display name.
            public_key: Public key for signature verification.
            metadata: Optional additional publisher metadata.

        Raises:
            ValueError: If the publisher already exists.
        """
        if publisher_id in self._publishers:
            raise ValueError(
                f"Publisher '{publisher_id}' is already registered."
            )

        self._publishers[publisher_id] = {
            "publisher_id": publisher_id,
            "name": name,
            "public_key": public_key,
            "metadata": metadata or {},
            "packages": [],
            "verified": False,
            "registered_at": time.time(),
        }
        self._register_count += 1
        logger.info(
            "Registered publisher '%s' (%s).", publisher_id, name
        )

    def unregister_publisher(self, publisher_id: str) -> None:
        """Remove a publisher and all their packages.

        Args:
            publisher_id: Publisher identifier to remove.

        Raises:
            KeyError: If the publisher is not found.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        publisher = self._publishers[publisher_id]
        for pkg in publisher.get("packages", []):
            pkg_id = pkg.get("id", "")
            self._package_index.pop(pkg_id, None)

        del self._publishers[publisher_id]
        logger.info(
            "Unregistered publisher '%s'.", publisher_id
        )

    def get_publisher(
        self, publisher_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get publisher information by identifier.

        Args:
            publisher_id: Publisher identifier.

        Returns:
            Publisher details dictionary, or ``None`` if not found.
        """
        return self._publishers.get(publisher_id)

    def list_publishers(self) -> List[Dict[str, Any]]:
        """List all registered publishers.

        Returns:
            A list of publisher detail dictionaries.
        """
        return list(self._publishers.values())

    def verify_publisher(self, publisher_id: str) -> bool:
        """Verify a publisher's identity.

        Checks that the publisher exists and has a valid public key.

        Args:
            publisher_id: Publisher identifier to verify.

        Returns:
            ``True`` if the publisher is verified.
        """
        publisher = self._publishers.get(publisher_id)
        if publisher is None:
            return False

        self._verify_count += 1
        verified = bool(publisher.get("public_key"))
        if verified:
            publisher["verified"] = True
        return verified

    def add_package(
        self, publisher_id: str, package_info: Dict[str, Any]
    ) -> None:
        """Register a package under a publisher.

        Args:
            publisher_id: The owning publisher's identifier.
            package_info: Dictionary with package metadata (must
                include ``id`` and ``version``).

        Raises:
            KeyError: If the publisher is not found.
            ValueError: If package_info lacks required fields.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        pkg_id = package_info.get("id")
        if not pkg_id:
            raise ValueError(
                "Package info must contain an 'id' field."
            )

        publisher = self._publishers[publisher_id]
        packages = publisher.setdefault("packages", [])

        for i, existing in enumerate(packages):
            if existing.get("id") == pkg_id:
                packages[i] = package_info
                self._package_index[pkg_id] = publisher_id
                logger.debug(
                    "Updated package '%s' for publisher '%s'.",
                    pkg_id,
                    publisher_id,
                )
                return

        packages.append(package_info)
        self._package_index[pkg_id] = publisher_id
        logger.info(
            "Added package '%s' for publisher '%s'.",
            pkg_id,
            publisher_id,
        )

    def get_packages(
        self, publisher_id: str
    ) -> List[Dict[str, Any]]:
        """Get all packages registered under a publisher.

        Args:
            publisher_id: Publisher identifier.

        Returns:
            A list of package metadata dictionaries.
        """
        publisher = self._publishers.get(publisher_id)
        if publisher is None:
            return []
        return publisher.get("packages", [])

    def search_packages(self, query: str) -> List[Dict[str, Any]]:
        """Search for packages across all publishers.

        Args:
            query: Search string to match against package id,
                name, or description.

        Returns:
            A list of matching package metadata dictionaries.
        """
        if not query:
            results: List[Dict[str, Any]] = []
            for pub in self._publishers.values():
                results.extend(pub.get("packages", []))
            return results

        query_lower = query.lower()
        results: List[Dict[str, Any]] = []
        for pub in self._publishers.values():
            for pkg in pub.get("packages", []):
                pkg_id = str(pkg.get("id", "")).lower()
                pkg_name = str(pkg.get("name", "")).lower()
                pkg_desc = str(pkg.get("description", "")).lower()
                if (
                    query_lower in pkg_id
                    or query_lower in pkg_name
                    or query_lower in pkg_desc
                ):
                    enriched = dict(pkg)
                    enriched["publisher"] = pub.get("name", "")
                    results.append(enriched)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Return registry statistics.

        Returns:
            Dictionary with publisher and package counts.
        """
        total_packages = sum(
            len(p.get("packages", []))
            for p in self._publishers.values()
        )
        verified_publishers = sum(
            1
            for p in self._publishers.values()
            if p.get("verified", False)
        )
        return {
            "total_publishers": len(self._publishers),
            "verified_publishers": verified_publishers,
            "total_packages": total_packages,
            "register_count": self._register_count,
            "verify_count": self._verify_count,
        }