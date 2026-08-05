"""Route rewriting for ICYQuant Service Mesh.

Provides ``RouteRewriter`` for path, host, and header rewriting
rules applied to requests before forwarding to destinations.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RouteRewriter:
    """Rewrites request paths, hosts, and headers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rewrite_count = 0

    def rewrite_request(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        rewrite_rules: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Apply rewrite rules to a request."""
        headers = dict(headers or {})
        rewrite_rules = rewrite_rules or {}

        new_path = path
        new_headers = dict(headers)

        # Apply path rewrite
        path_rewrite = rewrite_rules.get("path_rewrite", "")
        if path_rewrite:
            new_path = self._apply_path_rewrite(
                path, path_rewrite
            )

        # Apply header rewrites
        header_rewrites = rewrite_rules.get("headers", {})
        if header_rewrites:
            for key, value in header_rewrites.items():
                if value is None:
                    new_headers.pop(key, None)
                else:
                    new_headers[key] = value

        # Apply host rewrite
        host_rewrite = rewrite_rules.get("host_rewrite", "")
        if host_rewrite:
            new_headers["host"] = host_rewrite

        with self._lock:
            self._rewrite_count += 1

        return {
            "path": new_path,
            "headers": new_headers,
            "rewritten": new_path != path or new_headers != headers,
        }

    def _apply_path_rewrite(
        self, original_path: str, rewrite_template: str
    ) -> str:
        """Apply a path rewrite template.

        Supports:
        - Exact replacement: /old -> /new
        - Prefix removal: /prefix/ -> /
        - Regex capture: /api/(.*) -> /internal/$1
        """
        if "->" in rewrite_template:
            parts = rewrite_template.split("->", 1)
            pattern = parts[0].strip()
            replacement = parts[1].strip()
            try:
                return re.sub(
                    pattern, replacement, original_path
                )
            except re.error:
                logger.warning(
                    "Invalid rewrite pattern: %s", pattern
                )
                return original_path

        if rewrite_template.endswith("/"):
            prefix = rewrite_template.rstrip("/")
            if original_path.startswith(
                rewrite_template.rstrip("/") + "/"
            ):
                return original_path[len(prefix):] or "/"
            return original_path

        return rewrite_template

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rewrite_count": self._rewrite_count,
            }
