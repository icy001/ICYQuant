"""Search engine for the plugin marketplace.

Provides :class:`MarketplaceSearch` for searching across plugin
metadata including name, description, tags, author, and capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketplaceSearch:
    """Search engine for the plugin marketplace.

    Searches across plugin metadata including names, descriptions,
    tags, author names, and capabilities. Supports filtering and
    sorting by popularity or recency.

    Usage::

        search = MarketplaceSearch()
        results = search.search("momentum")
        by_tag = search.search_by_tag("trading")
        popular = search.get_popular(limit=10)
    """

    def __init__(self) -> None:
        self._packages: List[Dict[str, Any]] = []
        self._search_count: int = 0
        self._last_query: str = ""

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for plugins matching a query.

        Args:
            query: Search string to match against plugin metadata.
            filters: Optional dictionary of filter criteria.

        Returns:
            A list of matching plugin metadata dictionaries.
        """
        self._search_count += 1
        self._last_query = query
        results: List[Dict[str, Any]] = []

        if not query:
            results = list(self._packages)
        else:
            query_lower = query.lower()
            for pkg in self._packages:
                if self._matches_query(pkg, query_lower):
                    results.append(pkg)

        if filters:
            results = self._apply_filters(results, filters)

        logger.debug(
            "Search '%s' returned %d results.", query, len(results)
        )
        return results

    def search_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Search for plugins by tag.

        Args:
            tag: Tag to filter by.

        Returns:
            A list of plugins with the specified tag.
        """
        tag_lower = tag.lower()
        results: List[Dict[str, Any]] = []
        for pkg in self._packages:
            tags = pkg.get("tags", [])
            if isinstance(tags, list) and any(
                str(t).lower() == tag_lower for t in tags
            ):
                results.append(pkg)
        return results

    def search_by_author(self, author: str) -> List[Dict[str, Any]]:
        """Search for plugins by author.

        Args:
            author: Author name to filter by.

        Returns:
            A list of plugins by the specified author.
        """
        author_lower = author.lower()
        results: List[Dict[str, Any]] = []
        for pkg in self._packages:
            pkg_author = str(pkg.get("author", "")).lower()
            if author_lower in pkg_author:
                results.append(pkg)
        return results

    def search_by_capability(
        self, capability: str
    ) -> List[Dict[str, Any]]:
        """Search for plugins by capability.

        Args:
            capability: Capability name to filter by.

        Returns:
            A list of plugins providing the specified capability.
        """
        cap_lower = capability.lower()
        results: List[Dict[str, Any]] = []
        for pkg in self._packages:
            caps = pkg.get("capabilities", [])
            if isinstance(caps, list) and any(
                str(c).lower() == cap_lower for c in caps
            ):
                results.append(pkg)
        return results

    def get_popular(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get the most popular plugins.

        Args:
            limit: Maximum number of results to return.

        Returns:
            A list of the most popular plugin metadata dictionaries,
            sorted by download count or rating.
        """
        sorted_packages = sorted(
            self._packages,
            key=lambda p: p.get("downloads", 0),
            reverse=True,
        )
        return sorted_packages[:limit]

    def get_recently_updated(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recently updated plugins.

        Args:
            limit: Maximum number of results to return.

        Returns:
            A list of recently updated plugin metadata dictionaries,
            sorted by update timestamp.
        """
        sorted_packages = sorted(
            self._packages,
            key=lambda p: p.get("updated_at", 0),
            reverse=True,
        )
        return sorted_packages[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Return search engine statistics.

        Returns:
            Dictionary with search count and package index info.
        """
        return {
            "search_count": self._search_count,
            "indexed_packages": len(self._packages),
            "last_query": self._last_query,
        }

    def index_packages(
        self, packages: List[Dict[str, Any]]
    ) -> None:
        """Index a list of packages for searching.

        Args:
            packages: List of package metadata dictionaries.
        """
        self._packages = list(packages)
        logger.info(
            "Indexed %d packages for search.", len(packages)
        )

    @staticmethod
    def _matches_query(
        package: Dict[str, Any], query_lower: str
    ) -> bool:
        """Check if a package matches a search query.

        Args:
            package: Package metadata dictionary.
            query_lower: Lowercase search query.

        Returns:
            ``True`` if the package matches the query.
        """
        searchable_fields = [
            "id",
            "name",
            "description",
            "author",
        ]
        for field in searchable_fields:
            value = str(package.get(field, "")).lower()
            if query_lower in value:
                return True

        tags = package.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if query_lower in str(tag).lower():
                    return True

        caps = package.get("capabilities", [])
        if isinstance(caps, list):
            for cap in caps:
                if query_lower in str(cap).lower():
                    return True

        return False

    @staticmethod
    def _apply_filters(
        results: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Apply filters to search results.

        Args:
            results: List of package dictionaries.
            filters: Dictionary of filter criteria.

        Returns:
            Filtered list of package dictionaries.
        """
        filtered: List[Dict[str, Any]] = []
        for pkg in results:
            matches = True
            for key, value in filters.items():
                pkg_value = pkg.get(key)
                if pkg_value != value:
                    matches = False
                    break
            if matches:
                filtered.append(pkg)
        return filtered