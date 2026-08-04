"""
Atomic snapshot manager.

Provides lock-free read, atomic write pattern for
configuration snapshots. Uses reference swapping
to ensure readers always see a consistent state.

Design:
    - Lock-free reads (just read the reference)
    - Single-writer model for writes
    - Version tracking for consistency verification
    - Snapshot chain for audit trail
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from .snapshot import DynamicSnapshot


class AtomicSnapshotManager:
    """
    Thread-safe atomic snapshot manager.

    Implements the Atomic Snapshot Swap pattern:
    - Readers always see a complete, immutable snapshot
    - Writers build new snapshots and atomically swap
    - No read locks needed (lock-free reads)
    - Version consistency guaranteed

    Usage:
        manager = AtomicSnapshotManager()

        # Write path
        new_snapshot = build_snapshot(...)
        manager.activate(new_snapshot)

        # Read path (lock-free)
        snapshot = manager.current()
        value = snapshot.get("server.port")
    """

    def __init__(
        self,
        snapshot_store: Optional[Any] = None,
    ) -> None:
        """
        Initialize atomic snapshot manager.

        Args:
            snapshot_store: Optional DynamicSnapshotStore for history.
        """
        self._snapshot_store = snapshot_store
        self._snapshot: Optional[DynamicSnapshot] = None
        self._lock = threading.Lock()
        self._version_counter = 0
        self._activated = threading.Event()

    @property
    def version(
        self,
    ) -> int:
        """Get current version (lock-free)."""
        return self._version_counter

    @property
    def current(
        self,
    ) -> Optional[DynamicSnapshot]:
        """
        Get current snapshot (lock-free read).

        This is an O(1) operation with no lock contention.
        The returned snapshot is immutable and thread-safe.

        Returns:
            Current snapshot or None if not initialized.
        """
        return self._snapshot

    def activate(
        self,
        new_snapshot: DynamicSnapshot,
    ) -> DynamicSnapshot:
        """
        Atomically activate a new snapshot.

        This is the write path:
        1. Assign version number
        2. Set parent version reference
        3. Atomically swap the reference

        Args:
            new_snapshot: New snapshot to activate.

        Returns:
            The activated snapshot (with version assigned).
        """
        with self._lock:
            old_version = self._snapshot.version if self._snapshot else None

            self._version_counter += 1
            new_snapshot.version = self._version_counter
            new_snapshot.parent_version = old_version

            # Atomic swap (Python reference assignment is atomic)
            self._snapshot = new_snapshot
            self._activated.set()

            # Also update the snapshot store if available
            if self._snapshot_store is not None:
                try:
                    self._snapshot_store._current = new_snapshot
                except Exception:
                    pass

            return new_snapshot

    def activate_if_newer(
        self,
        new_snapshot: DynamicSnapshot,
    ) -> bool:
        """
        Activate only if the new snapshot has a higher version.

        Args:
            new_snapshot: Candidate snapshot.

        Returns:
            True if activated, False if rejected.
        """
        with self._lock:
            if self._snapshot and new_snapshot.version <= self._snapshot.version:
                return False

            old_version = self._snapshot.version if self._snapshot else None
            self._version_counter += 1
            new_snapshot.version = self._version_counter
            new_snapshot.parent_version = old_version
            self._snapshot = new_snapshot
            self._activated.set()
            return True

    def get_value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value (lock-free).

        Args:
            key: Configuration key.
            default: Default value.

        Returns:
            Configuration value.
        """
        snapshot = self._snapshot
        if snapshot is None:
            return default
        return snapshot.get(key, default)

    def get_nested(
        self,
        key: str,
        default: Any = None,
        separator: str = ".",
    ) -> Any:
        """
        Get a nested configuration value (lock-free).

        Args:
            key: Dotted key.
            default: Default value.
            separator: Key separator.

        Returns:
            Configuration value.
        """
        snapshot = self._snapshot
        if snapshot is None:
            return default
        return snapshot.get_nested(key, default, separator)

    def wait_for_activation(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait for the first snapshot activation.

        Args:
            timeout: Timeout in seconds.

        Returns:
            True if activated, False on timeout.
        """
        return self._activated.wait(timeout=timeout)

    def is_initialized(
        self,
    ) -> bool:
        """Check if at least one snapshot has been activated."""
        return self._snapshot is not None

    def verify_consistency(
        self,
    ) -> Dict[str, Any]:
        """
        Verify snapshot consistency.

        Checks:
        1. Integrity (checksum)
        2. Version chain
        3. Parent reference

        Returns:
            Consistency report.
        """
        snapshot = self._snapshot
        if snapshot is None:
            return {"status": "empty", "valid": False}

        # Check integrity
        integrity_ok = snapshot.verify_integrity()

        # Check version chain
        chain_valid = True
        if snapshot.parent_version is not None:
            chain_valid = snapshot.parent_version < snapshot.version

        return {
            "status": "ok",
            "valid": integrity_ok and chain_valid,
            "version": snapshot.version,
            "checksum": snapshot.checksum,
            "integrity_ok": integrity_ok,
            "chain_valid": chain_valid,
        }
