"""File system watcher for the plugin loader subsystem.

Polling-based file watcher that monitors directories for plugin
changes (added, removed, modified, manifest changed). Uses file
modification timestamps to detect changes and supports debouncing
to prevent rapid-fire duplicate events.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_DEBOUNCE_SECONDS = 0.5

WATCHED_MANIFESTS = frozenset(
    ("manifest.yaml", "manifest.yml", "manifest.json")
)


class FileWatcher:
    """Polling-based file system watcher for plugin directories.

    Watches one or more directories for file changes and emits
    change dictionaries with ``type``, ``path``, and ``timestamp``
    keys. The watcher runs an async polling loop when started.

    Change event types:

    - ``"added"`` – a new file was detected.
    - ``"removed"`` – a previously known file disappeared.
    - ``"updated"`` – a file's modification time changed.
    - ``"manifest_changed"`` – a manifest file was added or updated.

    Attributes:
        poll_interval: Seconds between polling cycles.
        debounce_seconds: Minimum seconds between events for the
            same path and event type.
    """

    def __init__(
        self,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
    ) -> None:
        self._paths: Dict[str, Dict[str, float]] = {}
        self._running: bool = False
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds
        self._last_event_times: Dict[str, float] = {}
        self._pending_changes: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._stats: Dict[str, int] = {
            "polls": 0,
            "changes_detected": 0,
            "errors": 0,
        }

    async def start(self, paths: List[str]) -> None:
        """Start watching the given directory paths.

        Begins an async polling loop that periodically checks
        for file changes. If the watcher is already running,
        the new paths are added to the watch list.

        Args:
            paths: Directory paths to watch.
        """
        if not paths:
            return

        async with self._lock:
            for path in paths:
                self._add_path_locked(path)

            if self._running:
                return

            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info(
                "File watcher started watching %d path(s).",
                len(self._paths),
            )

    async def stop(self) -> None:
        """Stop the watcher's polling loop.

        Cancels the background task and waits for it to finish.
        """
        async with self._lock:
            if not self._running:
                return
            self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("File watcher stopped.")

    async def poll(self) -> List[Dict[str, Any]]:
        """Poll for changes and return detected events.

        Runs a single polling cycle across all watched paths
        and returns any changes detected. This can be called
        manually in addition to the automatic polling loop.

        Returns:
            A list of change dictionaries, each with ``type``,
            ``path``, and ``timestamp`` keys.
        """
        async with self._lock:
            paths = list(self._paths.items())

        changes: List[Dict[str, Any]] = []
        for path_str, snapshot in paths:
            try:
                path_changes = self._detect_changes(path_str, snapshot)
                changes.extend(path_changes)
            except Exception as exc:
                self._stats["errors"] += 1
                logger.exception(
                    "Error polling path '%s': %s", path_str, exc
                )

        if changes:
            async with self._lock:
                self._pending_changes.extend(changes)
                self._stats["changes_detected"] += len(changes)

        self._stats["polls"] += 1
        return changes

    def is_running(self) -> bool:
        """Return whether the watcher's polling loop is active.

        Returns:
            ``True`` if the watcher is currently running.
        """
        return self._running

    def add_path(self, path: str) -> None:
        """Add a directory path to watch.

        Args:
            path: Directory path to begin watching.
        """
        if not path:
            return
        self._add_path_locked(path)
        logger.debug("Added watch path '%s'.", path)

    def remove_path(self, path: str) -> None:
        """Stop watching a directory path.

        Args:
            path: Directory path to stop watching.
        """
        if path in self._paths:
            del self._paths[path]
            logger.debug("Removed watch path '%s'.", path)

    def get_changes(self) -> List[Dict[str, Any]]:
        """Get and clear pending change events.

        Returns:
            A list of pending change dictionaries. Each dict has
            ``type``, ``path``, and ``timestamp`` keys.
        """
        changes = list(self._pending_changes)
        self._pending_changes.clear()
        return changes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the watcher state to a dictionary.

        Returns:
            A dictionary with watcher configuration and stats.
        """
        return {
            "running": self._running,
            "watched_paths": list(self._paths.keys()),
            "poll_interval": self._poll_interval,
            "debounce_seconds": self._debounce_seconds,
            "pending_changes": len(self._pending_changes),
            "stats": dict(self._stats),
        }

    async def _poll_loop(self) -> None:
        """Background polling loop that runs until stopped."""
        while self._running:
            try:
                await self.poll()
            except Exception as exc:
                self._stats["errors"] += 1
                logger.exception(
                    "File watcher poll loop error: %s", exc
                )
            await asyncio.sleep(self._poll_interval)

    def _add_path_locked(self, path: str) -> None:
        """Add a path to watch (must be called with lock held)."""
        if path not in self._paths:
            snapshot = self._snapshot_path(Path(path))
            self._paths[path] = snapshot

    def _detect_changes(
        self, path: str, snapshot: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect file changes in a watched path since the last snapshot.

        Updates the snapshot in place and returns a list of change
        dictionaries.

        Args:
            path: The watched directory path.
            snapshot: Previous file modification times.

        Returns:
            List of change dictionaries.
        """
        changes: List[Dict[str, Any]] = []
        current = self._snapshot_path(Path(path))
        now = time.time()

        for file_path, mtime in current.items():
            if file_path not in snapshot:
                is_manifest = (
                    os.path.basename(file_path) in WATCHED_MANIFESTS
                )
                event_type = (
                    "manifest_changed" if is_manifest else "added"
                )
                change = self._make_change(
                    event_type, file_path, now
                )
                if self._should_emit(change):
                    changes.append(change)
            elif mtime != snapshot[file_path]:
                is_manifest = (
                    os.path.basename(file_path) in WATCHED_MANIFESTS
                )
                event_type = (
                    "manifest_changed" if is_manifest else "updated"
                )
                change = self._make_change(
                    event_type, file_path, now
                )
                if self._should_emit(change):
                    changes.append(change)

        for file_path in list(snapshot.keys()):
            if file_path not in current:
                change = self._make_change("removed", file_path, now)
                if self._should_emit(change):
                    changes.append(change)

        snapshot.clear()
        snapshot.update(current)
        return changes

    def _should_emit(self, change: Dict[str, Any]) -> bool:
        """Apply debouncing to prevent rapid-fire duplicate events."""
        key = f"{change['path']}:{change['type']}"
        now = change["timestamp"]
        last = self._last_event_times.get(key, 0.0)
        if (now - last) < self._debounce_seconds:
            return False
        self._last_event_times[key] = now
        return True

    @staticmethod
    def _make_change(
        event_type: str, path: str, timestamp: float
    ) -> Dict[str, Any]:
        """Build a change event dictionary."""
        return {
            "type": event_type,
            "path": path,
            "timestamp": timestamp,
        }

    @staticmethod
    def _snapshot_path(path: Path) -> Dict[str, float]:
        """Take a snapshot of file modification times under a path."""
        snapshot: Dict[str, float] = {}
        if not path.exists() or not path.is_dir():
            return snapshot
        try:
            for root, _dirs, files in os.walk(str(path)):
                for filename in files:
                    if filename.startswith("."):
                        continue
                    full = os.path.join(root, filename)
                    try:
                        snapshot[full] = os.path.getmtime(full)
                    except OSError:
                        continue
        except OSError:
            return snapshot
        return snapshot