"""Dataset Registry — in-memory index for fast dataset lookups.

Supports multi-dimensional indexing by name, source, tags, and status.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DatasetRegistry:
    """In-memory dataset index with multi-dimensional lookups.

    Indexes:
    * By ID (primary)
    * By name
    * By source
    * By tags
    * By status
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._by_name: Dict[str, str] = {}  # name → id
        self._by_source: Dict[str, Set[str]] = {}
        self._by_tag: Dict[str, Set[str]] = {}
        self._by_status: Dict[str, Set[str]] = {}

    # ── registration ──────────────────────────────────────────────────────

    def register(self, dataset_id: str, data: Dict[str, Any]) -> None:
        """Register a dataset in all indexes."""
        if dataset_id in self._by_id:
            self._unregister_indexes(dataset_id)

        self._by_id[dataset_id] = data

        name = data.get("name", "")
        if name:
            self._by_name[name] = dataset_id

        source = data.get("source", "")
        self._by_source.setdefault(source, set()).add(dataset_id)

        for tag in data.get("tags", []):
            self._by_tag.setdefault(tag, set()).add(dataset_id)

        status = data.get("status", "active")
        self._by_status.setdefault(status, set()).add(dataset_id)

        logger.debug("Registered dataset: %s", dataset_id)

    def unregister(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Remove a dataset from all indexes."""
        data = self._by_id.pop(dataset_id, None)
        if data is None:
            return None
        self._unregister_indexes(dataset_id)
        return data

    # ── retrieval ─────────────────────────────────────────────────────────

    def get(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(dataset_id)

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        dataset_id = self._by_name.get(name)
        if dataset_id:
            return self._by_id.get(dataset_id)
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._by_id.values())

    def list_by_source(self, source: str) -> List[Dict[str, Any]]:
        ids = self._by_source.get(source, set())
        return [self._by_id[did] for did in ids if did in self._by_id]

    def list_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        ids = self._by_tag.get(tag, set())
        return [self._by_id[did] for did in ids if did in self._by_id]

    def list_by_status(self, status: str) -> List[Dict[str, Any]]:
        ids = self._by_status.get(status, set())
        return [self._by_id[did] for did in ids if did in self._by_id]

    def list_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Datasets matching ALL given tags."""
        if not tags:
            return []
        result_ids = self._by_tag.get(tags[0], set()).copy()
        for tag in tags[1:]:
            result_ids &= self._by_tag.get(tag, set())
        return [self._by_id[did] for did in result_ids if did in self._by_id]

    # ── stats ─────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._by_id)

    def summary(self) -> Dict[str, Any]:
        return {
            "total": self.count,
            "by_source": {k: len(v) for k, v in self._by_source.items()},
            "by_tag": {k: len(v) for k, v in self._by_tag.items()},
            "by_status": {k: len(v) for k, v in self._by_status.items()},
        }

    # ── internal ──────────────────────────────────────────────────────────

    def _unregister_indexes(self, dataset_id: str) -> None:
        data = self._by_id.get(dataset_id)
        if data is None:
            return
        name = data.get("name", "")
        if name and self._by_name.get(name) == dataset_id:
            del self._by_name[name]
        for source_set in self._by_source.values():
            source_set.discard(dataset_id)
        for tag_set in self._by_tag.values():
            tag_set.discard(dataset_id)
        for status_set in self._by_status.values():
            status_set.discard(dataset_id)

    def __repr__(self) -> str:
        return f"DatasetRegistry(datasets={self.count})"
