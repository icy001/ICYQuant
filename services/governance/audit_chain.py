"""
Audit Chain — hash-linked chain of audit events for tamper detection.

Each link:  previous_hash + event_hash → combined hash
The combined hash becomes the previous_hash for the next link.

Any modification to any event breaks the entire chain.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .audit_hash import AuditHash


@dataclass
class ChainLink:
    """A single link in the audit hash chain."""

    index: int
    event_id: str
    event_hash: str
    previous_hash: str
    chain_hash: str  # SHA256(previous_hash + event_hash)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "previous_hash": self.previous_hash,
            "chain_hash": self.chain_hash,
            "timestamp": self.timestamp,
        }


class AuditChain:
    """Hash chain of governance audit events.

    Properties:
      - Append-only: links can only be added, never removed
      - Hash-linked: each link contains previous_hash
      - Tamper-evident: any modification breaks the chain
    """

    GENESIS_HASH = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self):
        self._links: List[ChainLink] = []

    def append(self, event_hash: str, event_id: str,
               timestamp: Optional[float] = None) -> ChainLink:
        """Append a new link to the chain."""
        previous_hash = self.last_hash
        combined = f"{previous_hash}{event_hash}"
        chain_hash = AuditHash.compute_content_hash(combined)

        link = ChainLink(
            index=len(self._links),
            event_id=event_id,
            event_hash=event_hash,
            previous_hash=previous_hash,
            chain_hash=chain_hash,
            timestamp=timestamp or time.time(),
        )
        self._links.append(link)
        return link

    def verify(self) -> Dict[str, Any]:
        """Verify the entire chain for integrity.

        Returns dict with 'valid' and 'issues' keys.
        """
        issues: List[Dict[str, Any]] = []

        for i, link in enumerate(self._links):
            expected_previous = self.GENESIS_HASH if i == 0 else self._links[i - 1].chain_hash
            if link.previous_hash != expected_previous:
                issues.append({
                    "index": i,
                    "event_id": link.event_id,
                    "type": "BROKEN_PREVIOUS_HASH",
                    "expected": expected_previous,
                    "actual": link.previous_hash,
                })

            combined = f"{link.previous_hash}{link.event_hash}"
            expected_chain = AuditHash.compute_content_hash(combined)
            if link.chain_hash != expected_chain:
                issues.append({
                    "index": i,
                    "event_id": link.event_id,
                    "type": "CHAIN_HASH_MISMATCH",
                    "expected": expected_chain,
                    "actual": link.chain_hash,
                })

        return {
            "valid": len(issues) == 0,
            "chain_length": len(self._links),
            "issues": issues,
        }

    def verify_link(self, index: int) -> Dict[str, Any]:
        """Verify a single chain link."""
        if index < 0 or index >= len(self._links):
            return {"valid": False, "issues": [{"type": "OUT_OF_RANGE"}]}

        link = self._links[index]
        issues: List[Dict[str, Any]] = []

        expected_previous = self.GENESIS_HASH if index == 0 else self._links[index - 1].chain_hash
        if link.previous_hash != expected_previous:
            issues.append({
                "type": "BROKEN_PREVIOUS_HASH",
                "expected": expected_previous,
                "actual": link.previous_hash,
            })

        combined = f"{link.previous_hash}{link.event_hash}"
        expected_chain = AuditHash.compute_content_hash(combined)
        if link.chain_hash != expected_chain:
            issues.append({
                "type": "CHAIN_HASH_MISMATCH",
                "expected": expected_chain,
                "actual": link.chain_hash,
            })

        return {"valid": len(issues) == 0, "link": link.to_dict(), "issues": issues}

    # ── Properties ──

    @property
    def length(self) -> int:
        return len(self._links)

    @property
    def last_hash(self) -> str:
        if not self._links:
            return self.GENESIS_HASH
        return self._links[-1].chain_hash

    @property
    def last_event_id(self) -> Optional[str]:
        if not self._links:
            return None
        return self._links[-1].event_id

    def get_link(self, index: int) -> Optional[ChainLink]:
        """Get a specific chain link by index."""
        if 0 <= index < len(self._links):
            return self._links[index]
        return None

    def get_link_by_event(self, event_id: str) -> Optional[ChainLink]:
        """Find a chain link by event ID."""
        for link in self._links:
            if link.event_id == event_id:
                return link
        return None

    def to_list(self) -> List[Dict[str, Any]]:
        """Export entire chain as a list of dicts."""
        return [link.to_dict() for link in self._links]
