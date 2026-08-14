"""Command fingerprint — canonical identity of a control command (Commit 29 Part 1.4 §6-8).

A fingerprint binds principal, resource, action, target and parameters into a
stable SHA-256 digest. Canonical JSON (sorted keys, compact separators) means
two dicts that are business-identical but ordered differently hash the same;
any mutation of the command produces a different fingerprint (§50).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any


def _canonical_json(payload: dict[str, Any]) -> str:
    """Stable serialization — order and whitespace must not matter (§8)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def fingerprint_command(command: Any) -> str:
    """Canonical SHA-256 fingerprint of a control command (§6-7).

    ``principal_id`` is preferred when present; the legacy ``ControlCommand``
    carries the principal as ``requested_by`` (§7).
    """
    target = getattr(command, "target", None)
    payload = {
        "principal_id": getattr(command, "principal_id", None)
        or getattr(command, "requested_by", ""),
        "resource": getattr(command, "resource", ""),
        "action": getattr(command, "action", ""),
        "target": asdict(target) if target is not None else None,
        "parameters": getattr(command, "parameters", {}),
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
