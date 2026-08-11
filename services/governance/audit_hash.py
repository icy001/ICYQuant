"""
Audit Hash — hash computation utilities for audit events and chains.

Provides SHA-256 based hashing for:
  - Individual audit events (content hash)
  - Hash chain links (previous_hash + current_content)
  - Decision snapshots
  - Combined state hashes
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


class AuditHash:
    """Hash computation utilities for audit integrity."""

    HASH_ALGORITHM = "sha256"

    @staticmethod
    def compute_event_hash(event_data: Dict[str, Any]) -> str:
        """Compute the content hash of an audit event.

        Hash = SHA256(event_id + event_type + entity_type + entity_id
                       + actor_id + action + outcome + timestamp + context_json)
        """
        data_str = json.dumps(
            {
                "event_id": event_data.get("event_id", ""),
                "event_type": str(event_data.get("event_type", "")),
                "entity_type": event_data.get("entity_type", ""),
                "entity_id": event_data.get("entity_id", ""),
                "actor_id": event_data.get("actor", {}).get("actor_id", ""),
                "action": str(event_data.get("action", "")),
                "outcome": str(event_data.get("outcome", "")),
                "reason": event_data.get("reason", ""),
                "timestamp": event_data.get("timestamp", 0),
                "context": event_data.get("context", {}),
                "previous_hash": event_data.get("previous_hash", ""),
            },
            sort_keys=True,
            default=str,
        )
        return f"sha256:{hashlib.sha256(data_str.encode('utf-8')).hexdigest()}"

    @staticmethod
    def compute_chain_hash(previous_hash: str, event_data: Dict[str, Any]) -> str:
        """Compute the chained hash linking to the previous event.

        ChainHash = SHA256(previous_hash + event_content_hash)
        """
        content_hash = AuditHash.compute_event_hash(event_data)
        combined = f"{previous_hash}{content_hash}"
        return f"sha256:{hashlib.sha256(combined.encode('utf-8')).hexdigest()}"

    @staticmethod
    def compute_snapshot_hash(snapshot_data: Dict[str, Any]) -> str:
        """Compute hash of a decision snapshot.

        Includes ALL snapshot components: market, risk, policy,
        authority, approval, allocation.
        """
        data_str = json.dumps(snapshot_data, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(data_str.encode('utf-8')).hexdigest()}"

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute hash of arbitrary string content."""
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

    @staticmethod
    def verify_hash(content: str, expected_hash: str) -> bool:
        """Verify that content matches expected hash."""
        computed = AuditHash.compute_content_hash(content)
        return computed == expected_hash

    @staticmethod
    def strip_algorithm(hash_str: str) -> str:
        """Remove algorithm prefix, returning raw hex digest."""
        if ":" in hash_str:
            return hash_str.split(":", 1)[1]
        return hash_str

    @staticmethod
    def raw_sha256(data: str) -> str:
        """Return raw SHA-256 hex digest of data."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
