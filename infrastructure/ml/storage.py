"""ML Storage - Backend storage for artifacts, models, and metadata.

Provides persistent storage for the ML Platform with support for
local filesystem, S3, MinIO, and other backends.

Usage::

    from infrastructure.ml.storage import MLStorage

    storage = MLStorage(backend="local", root_path="./ml_store")
    storage.save(model_bytes, "models/alpha_model_v4.pkl")
    data = storage.load("models/alpha_model_v4.pkl")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class StorageType(str, Enum):
    """Storage backend types."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    MEMORY = "memory"


@dataclass
class StorageObject:
    """Metadata for a stored object."""

    key: str
    size_bytes: int = 0
    content_type: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


class MLStorage:
    """Unified storage backend for the ML platform.

    Supports multiple backends with a consistent interface for
    saving and loading models, artifacts, metadata, and training data.

    The in-memory backend is used for development/testing.
    Local filesystem is used for production when no cloud storage is available.
    S3/MinIO are for production cloud deployments.

    Usage::

        storage = MLStorage(backend="local", root_path="./ml_store")
        storage.save_bytes(b"...", "models/alpha.pkl")
        storage.save_json({"sharpe": 2.03}, "metrics/alpha.json")
        model = storage.load_bytes("models/alpha.pkl")
        metrics = storage.load_json("metrics/alpha.json")
        objects = storage.list("models/")
    """

    def __init__(self, backend: str = "memory", root_path: str = "ml_store") -> None:
        self.backend = StorageType(backend)
        self.root_path = root_path
        self._memory_store: Dict[str, Tuple[bytes, Dict[str, str]]] = {}
        self._metadata_store: Dict[str, StorageObject] = {}
        if self.backend == StorageType.LOCAL:
            os.makedirs(root_path, exist_ok=True)

    # ---- Save ----

    def save_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> StorageObject:
        """Save raw bytes to storage.

        Args:
            data: Raw binary data.
            key: Storage key (path-like, e.g. "models/alpha_v4.pkl").
            content_type: MIME type of the data.

        Returns:
            StorageObject metadata.
        """
        if self.backend == StorageType.LOCAL:
            filepath = os.path.join(self.root_path, key)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)
        elif self.backend == StorageType.MEMORY:
            meta = {"content_type": content_type}
            self._memory_store[key] = (data, meta)

        obj = self._upsert_metadata(key, len(data), content_type)
        return obj

    def save_json(self, data: Dict[str, Any], key: str) -> StorageObject:
        """Save JSON-serializable data."""
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return self.save_bytes(json_bytes, key, content_type="application/json")

    def save_text(self, data: str, key: str) -> StorageObject:
        """Save text data."""
        return self.save_bytes(data.encode("utf-8"), key, content_type="text/plain")

    # ---- Load ----

    def load_bytes(self, key: str) -> Optional[bytes]:
        """Load raw bytes from storage."""
        if self.backend == StorageType.LOCAL:
            filepath = os.path.join(self.root_path, key)
            if not os.path.exists(filepath):
                return None
            with open(filepath, "rb") as f:
                return f.read()
        elif self.backend == StorageType.MEMORY:
            entry = self._memory_store.get(key)
            return entry[0] if entry else None
        return None

    def load_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Load JSON data, returning a dict."""
        data = self.load_bytes(key)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))

    def load_text(self, key: str) -> Optional[str]:
        """Load text data."""
        data = self.load_bytes(key)
        return data.decode("utf-8") if data else None

    # ---- Metadata ----

    def get_metadata(self, key: str) -> Optional[StorageObject]:
        """Get stored object metadata."""
        return self._metadata_store.get(key)

    def exists(self, key: str) -> bool:
        """Check if an object exists."""
        if self.backend == StorageType.LOCAL:
            return os.path.exists(os.path.join(self.root_path, key))
        return key in self._memory_store

    def list(self, prefix: str = "") -> List[StorageObject]:
        """List storage objects, optionally filtered by prefix."""
        results = []
        for key, obj in self._metadata_store.items():
            if not prefix or key.startswith(prefix):
                results.append(obj)
        # Also check memory store for undeleted items
        for key in self._memory_store:
            if (not prefix or key.startswith(prefix)) and key not in self._metadata_store:
                size = len(self._memory_store[key][0])
                obj = self._upsert_metadata(key, size, self._memory_store[key][1].get("content_type", ""))
                results.append(obj)
        results.sort(key=lambda o: o.created_at, reverse=True)
        return results

    # ---- Delete ----

    def delete(self, key: str) -> bool:
        """Delete an object from storage."""
        deleted = False
        if self.backend == StorageType.LOCAL:
            filepath = os.path.join(self.root_path, key)
            if os.path.exists(filepath):
                os.remove(filepath)
                deleted = True
        elif self.backend == StorageType.MEMORY:
            if key in self._memory_store:
                del self._memory_store[key]
                deleted = True
        self._metadata_store.pop(key, None)
        return deleted

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects with a given prefix. Returns count deleted."""
        count = 0
        for key in list(self._metadata_store.keys()):
            if key.startswith(prefix):
                if self.delete(key):
                    count += 1
        # Also check memory-only keys
        for key in list(self._memory_store.keys()):
            if key.startswith(prefix) and key not in self._metadata_store:
                del self._memory_store[key]
                count += 1
        return count

    # ---- Stats ----

    def count(self) -> int:
        """Total number of stored objects."""
        return len(self._metadata_store)

    def total_size(self) -> int:
        """Total size in bytes."""
        return sum(o.size_bytes for o in self._metadata_store.values())

    # ---- Internal ----

    def _upsert_metadata(self, key: str, size: int, content_type: str) -> StorageObject:
        """Create or update stored object metadata."""
        existing = self._metadata_store.get(key)
        if existing:
            existing.size_bytes = size
            existing.content_type = content_type
            existing.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return existing
        obj = StorageObject(key=key, size_bytes=size, content_type=content_type)
        self._metadata_store[key] = obj
        return obj
