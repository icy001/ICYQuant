"""
Configuration history tracking.

Records complete configuration change history
for audit, traceability, and difference comparison.

Tracks:
- Version number
- Source of change
- Operator
- Diff (old → new)
- Timestamp
- Reason for change
"""

from __future__ import annotations

import copy
import difflib
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class ConfigChangeEntry:
    """
    Records a single configuration change.

    Attributes:
        version: New version number.
        previous_version: Previous version number.
        source: Source of the change.
        operator: Who made the change.
        reason: Reason for the change.
        timestamp: When the change occurred.
        changed_keys: List of keys that changed.
        old_values: Old values for changed keys.
        new_values: New values for changed keys.
    """

    def __init__(
        self,
        version: int,
        previous_version: Optional[int],
        source: str,
        operator: str,
        reason: str,
        changed_keys: List[str],
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
    ) -> None:
        self.version = version
        self.previous_version = previous_version
        self.source = source
        self.operator = operator
        self.reason = reason
        self.timestamp = datetime.utcnow()
        self.changed_keys = changed_keys
        self.old_values = old_values
        self.new_values = new_values

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "previous_version": self.previous_version,
            "source": self.source,
            "operator": self.operator,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "changed_keys": self.changed_keys,
            "old_values": copy.deepcopy(self.old_values),
            "new_values": copy.deepcopy(self.new_values),
        }

    def get_diff(
        self,
    ) -> str:
        """Get a human-readable diff of the change."""
        old_str = json.dumps(self.old_values, indent=2, sort_keys=True, default=str)
        new_str = json.dumps(self.new_values, indent=2, sort_keys=True, default=str)

        diff = difflib.unified_diff(
            old_str.splitlines(keepends=True),
            new_str.splitlines(keepends=True),
            fromfile=f"v{self.previous_version}",
            tofile=f"v{self.version}",
        )
        return "".join(diff)


class ConfigurationHistory:
    """
    Tracks complete configuration change history.

    Provides full audit trail for:
    - Compliance verification
    - Operational traceability
    - Difference comparison between versions

    Usage:
        history = ConfigurationHistory()

        # Record a change
        history.record_change(
            version=5,
            previous_version=4,
            old_values={"server.port": 8080},
            new_values={"server.port": 9090},
            source="file",
            operator="admin",
            reason="port change",
        )

        # Get history
        changes = history.get_changes()

        # Compare versions
        diff = history.compare_versions(4, 5)
    """

    def __init__(
        self,
        max_entries: int = 500,
    ) -> None:
        """
        Initialize configuration history.

        Args:
            max_entries: Maximum history entries to keep.
        """
        self._entries: List[ConfigChangeEntry] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def record_change(
        self,
        version: int,
        previous_version: Optional[int],
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        source: str = "file",
        operator: str = "system",
        reason: str = "",
    ) -> ConfigChangeEntry:
        """
        Record a configuration change.

        Args:
            version: New version number.
            previous_version: Previous version number.
            old_values: Previous configuration values.
            new_values: New configuration values.
            source: Source of the change.
            operator: Who made the change.
            reason: Reason for the change.

        Returns:
            ConfigChangeEntry.
        """
        # Calculate changed keys
        changed_keys = self._find_changed_keys(old_values, new_values)

        # Extract old and new values for changed keys
        old_changed = {
            k: old_values.get(k) for k in changed_keys
        }
        new_changed = {
            k: new_values.get(k) for k in changed_keys
        }

        entry = ConfigChangeEntry(
            version=version,
            previous_version=previous_version,
            source=source,
            operator=operator,
            reason=reason,
            changed_keys=changed_keys,
            old_values=old_changed,
            new_values=new_changed,
        )

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries.pop(0)

        return entry

    def get_changes(
        self,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get configuration change history.

        Args:
            limit: Maximum number of entries.
            source: Filter by source.

        Returns:
            List of change entries.
        """
        with self._lock:
            entries = self._entries
            if source:
                entries = [e for e in entries if e.source == source]
            if limit:
                entries = entries[-limit:]
            return [e.to_dict() for e in entries]

    def get_change(
        self,
        version: int,
    ) -> Optional[ConfigChangeEntry]:
        """
        Get a specific version change.

        Args:
            version: Version to look up.

        Returns:
            ConfigChangeEntry or None.
        """
        with self._lock:
            for entry in reversed(self._entries):
                if entry.version == version:
                    return entry
        return None

    def compare_versions(
        self,
        from_version: int,
        to_version: int,
    ) -> Dict[str, Any]:
        """
        Compare two versions.

        Args:
            from_version: Source version.
            to_version: Target version.

        Returns:
            Comparison result.
        """
        from_entry = self.get_change(from_version)
        to_entry = self.get_change(to_version)

        if from_entry is None or to_entry is None:
            return {
                "error": f"Versions not found: {from_version} → {to_version}",
            }

        changed_keys = set(from_entry.changed_keys) | set(to_entry.changed_keys)
        old_values = from_entry.old_values
        new_values = to_entry.new_values

        diff = difflib.unified_diff(
            json.dumps(old_values, indent=2, sort_keys=True, default=str).splitlines(keepends=True),
            json.dumps(new_values, indent=2, sort_keys=True, default=str).splitlines(keepends=True),
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
        )

        return {
            "from_version": from_version,
            "to_version": to_version,
            "changed_keys": sorted(changed_keys),
            "diff": "".join(diff),
            "operator": to_entry.operator,
            "reason": to_entry.reason,
            "timestamp": to_entry.timestamp.isoformat(),
        }

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get history statistics."""
        with self._lock:
            if not self._entries:
                return {"total_changes": 0}

            operators = set(e.operator for e in self._entries)
            sources = set(e.source for e in self._entries)

            return {
                "total_changes": len(self._entries),
                "operators": list(operators),
                "sources": list(sources),
                "latest_version": self._entries[-1].version,
                "first_version": self._entries[0].version,
            }

    @staticmethod
    def _find_changed_keys(
        old: Dict[str, Any],
        new: Dict[str, Any],
    ) -> List[str]:
        """Find keys that changed between two configs."""
        all_keys = set(old.keys()) | set(new.keys())
        changed = []
        for key in sorted(all_keys):
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changed.append(key)
        return changed
