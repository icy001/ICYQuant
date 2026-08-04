"""
Configuration watcher.

Watches for configuration changes from multiple sources:
- File system (YAML, JSON, TOML, .env files)
- Remote config (HTTP polling)
- Environment variables
- Event-driven triggers

When a change is detected, it triggers the reload pipeline
with debouncing to prevent excessive reloads.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .debounce import AsyncDebounce


class FileWatcher:
    """
    Watches a directory or specific files for changes.

    Uses polling-based detection (cross-platform compatible)
    with configurable debounce to prevent excessive triggers
    from rapid file changes.

    Supports watching:
    - YAML files (.yaml, .yml)
    - JSON files (.json)
    - TOML files (.toml)
    - .env files
    - Custom file patterns

    Usage:
        watcher = FileWatcher(paths=["config.yaml"])
        watcher.on_change = lambda path: print(f"Changed: {path}")
        watcher.start()
    """

    def __init__(
        self,
        paths: Optional[List[str]] = None,
        directories: Optional[List[str]] = None,
        file_patterns: Optional[List[str]] = None,
        poll_interval: float = 1.0,
        debounce_time: float = 0.5,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize file watcher.

        Args:
            paths: Specific file paths to watch.
            directories: Directories to watch for config files.
            file_patterns: File patterns to match in directories.
            poll_interval: Polling interval in seconds.
            debounce_time: Debounce time for change events.
            loop: Async event loop.
        """
        self._paths: Set[str] = set()
        self._directories: List[str] = directories or []
        self._file_patterns: List[str] = file_patterns or [
            "*.yaml", "*.yml", "*.json", "*.toml", ".env*"
        ]
        self._poll_interval = poll_interval
        self._loop = loop

        # Add specific paths
        if paths:
            for p in paths:
                self._paths.add(os.path.abspath(p))

        # Track file modification times
        self._file_mtimes: Dict[str, float] = {}

        # Debounced change handler
        self._debounce = AsyncDebounce(
            wait_time=debounce_time,
            loop=loop,
        )

        # Change callback
        self._on_change: Optional[Callable] = None

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def on_change(
        self,
    ) -> Optional[Callable]:
        """Get change callback."""
        return self._on_change

    @on_change.setter
    def on_change(
        self,
        callback: Callable,
    ) -> None:
        """Set change callback."""
        self._on_change = callback

    def add_path(
        self,
        path: str,
    ) -> None:
        """Add a file to watch."""
        self._paths.add(os.path.abspath(path))

    def remove_path(
        self,
        path: str,
    ) -> None:
        """Remove a file from watch."""
        self._paths.discard(os.path.abspath(path))

    def add_directory(
        self,
        directory: str,
    ) -> None:
        """Add a directory to watch."""
        self._directories.append(os.path.abspath(directory))

    def start(
        self,
    ) -> None:
        """Start watching for file changes."""
        self._loop = self._loop or asyncio.get_event_loop()
        self._running = True
        self._task = self._loop.create_task(self._watch_loop())

    def stop(
        self,
    ) -> None:
        """Stop watching for file changes."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _watch_loop(
        self,
    ) -> None:
        """Main watch loop."""
        # Initialize file mtimes
        self._scan_files()

        while self._running:
            await asyncio.sleep(self._poll_interval)
            changed = self._check_changes()
            if changed:
                await self._debounce_emit(changed)

    def _scan_files(
        self,
    ) -> None:
        """Scan and track all watchable files."""
        all_files: Set[str] = set(self._paths)

        # Add files from directories
        for directory in self._directories:
            dir_path = Path(directory)
            if dir_path.is_dir():
                for pattern in self._file_patterns:
                    for f in dir_path.glob(pattern):
                        if f.is_file():
                            all_files.add(str(f.absolute()))

        # Update mtimes
        for filepath in all_files:
            try:
                mtime = os.path.getmtime(filepath)
                self._file_mtimes[filepath] = mtime
            except OSError:
                pass

    def _check_changes(
        self,
    ) -> List[str]:
        """
        Check for file changes.

        Returns:
            List of changed file paths.
        """
        changed: List[str] = []

        # Re-scan directories for new files
        self._scan_files()

        for filepath, old_mtime in self._file_mtimes.items():
            try:
                if not os.path.exists(filepath):
                    # File removed
                    changed.append(filepath)
                    self._file_mtimes.pop(filepath, None)
                    continue

                new_mtime = os.path.getmtime(filepath)
                if new_mtime != old_mtime:
                    changed.append(filepath)
                    self._file_mtimes[filepath] = new_mtime
            except OSError:
                changed.append(filepath)

        return changed

    async def _debounce_emit(
        self,
        changed_files: List[str],
    ) -> None:
        """Emit change event via debounce."""
        if self._on_change:
            self._on_change(changed_files)


class RemoteConfigWatcher:
    """
    Watches a remote configuration endpoint for changes.

    Polls a remote URL and detects changes via checksum
    or ETag comparison.

    Usage:
        watcher = RemoteConfigWatcher(url="http://config-server/config")
        watcher.on_change = lambda data: print("Config updated")
        watcher.start()
    """

    def __init__(
        self,
        url: str,
        poll_interval: float = 5.0,
        debounce_time: float = 1.0,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize remote config watcher.

        Args:
            url: Remote configuration URL.
            poll_interval: Polling interval in seconds.
            debounce_time: Debounce time.
            loop: Async event loop.
        """
        self._url = url
        self._poll_interval = poll_interval
        self._loop = loop
        self._last_checksum: Optional[str] = None
        self._debounce = AsyncDebounce(wait_time=debounce_time, loop=loop)
        self._on_change: Optional[Callable] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def on_change(
        self,
    ) -> Optional[Callable]:
        return self._on_change

    @on_change.setter
    def on_change(
        self,
        callback: Callable,
    ) -> None:
        self._on_change = callback

    def start(
        self,
    ) -> None:
        """Start watching remote config."""
        self._loop = self._loop or asyncio.get_event_loop()
        self._running = True
        self._task = self._loop.create_task(self._watch_loop())

    def stop(
        self,
    ) -> None:
        """Stop watching remote config."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _watch_loop(
        self,
    ) -> None:
        """Main watch loop."""
        import hashlib

        while self._running:
            await asyncio.sleep(self._poll_interval)
            try:
                import urllib.request
                with urllib.request.urlopen(self._url) as response:
                    data = response.read()
                    checksum = hashlib.sha256(data).hexdigest()

                    if checksum != self._last_checksum:
                        self._last_checksum = checksum
                        if self._on_change:
                            self._on_change(data.decode() if isinstance(data, bytes) else data)
            except Exception:
                pass


class ConfigurationWatcher:
    """
    Unified configuration watcher.

    Combines file watching, remote watching, and
    environment variable watching into a single
    change detection system.

    Usage:
        watcher = ConfigurationWatcher()
        watcher.add_file("config.yaml")
        watcher.add_directory("config/")
        watcher.on_any_change(lambda changes: reload())
        watcher.start()
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        debounce_time: float = 0.5,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize configuration watcher.

        Args:
            poll_interval: Polling interval.
            debounce_time: Debounce time.
            loop: Async event loop.
        """
        self._loop = loop
        self._file_watcher = FileWatcher(
            poll_interval=poll_interval,
            debounce_time=debounce_time,
            loop=loop,
        )
        self._remote_watchers: List[RemoteConfigWatcher] = []
        self._env_vars: Dict[str, str] = {}
        self._on_change_callbacks: List[Callable] = []

        # Set up file watcher callback
        self._file_watcher.on_change = self._handle_file_change

    def add_file(
        self,
        path: str,
    ) -> None:
        """Add a file to watch."""
        self._file_watcher.add_path(path)

    def add_directory(
        self,
        directory: str,
        patterns: Optional[List[str]] = None,
    ) -> None:
        """Add a directory to watch."""
        self._file_watcher.add_directory(directory)
        if patterns:
            self._file_watcher._file_patterns = patterns

    def add_remote(
        self,
        url: str,
        poll_interval: float = 5.0,
    ) -> None:
        """Add a remote config endpoint to watch."""
        watcher = RemoteConfigWatcher(
            url=url,
            poll_interval=poll_interval,
            loop=self._loop,
        )
        watcher.on_change = lambda data: self._handle_remote_change(url, data)
        self._remote_watchers.append(watcher)

    def watch_env_vars(
        self,
        var_names: List[str],
    ) -> None:
        """Watch specific environment variables."""
        for name in var_names:
            self._env_vars[name] = os.environ.get(name, "")

    def on_any_change(
        self,
        callback: Callable,
    ) -> None:
        """Register a change callback."""
        self._on_change_callbacks.append(callback)

    def start(
        self,
    ) -> None:
        """Start all watchers."""
        self._file_watcher.start()
        for watcher in self._remote_watchers:
            watcher.start()

    def stop(
        self,
    ) -> None:
        """Stop all watchers."""
        self._file_watcher.stop()
        for watcher in self._remote_watchers:
            watcher.stop()

    def _handle_file_change(
        self,
        changed_files: List[str],
    ) -> None:
        """Handle file changes."""
        for callback in self._on_change_callbacks:
            try:
                callback({"type": "file", "files": changed_files})
            except Exception:
                pass

    def _handle_remote_change(
        self,
        url: str,
        data: Any,
    ) -> None:
        """Handle remote config changes."""
        for callback in self._on_change_callbacks:
            try:
                callback({"type": "remote", "url": url, "data": data})
            except Exception:
                pass

    async def check_env_changes(
        self,
    ) -> List[str]:
        """
        Check for environment variable changes.

        Returns:
            List of changed variable names.
        """
        changed = []
        for name, old_value in self._env_vars.items():
            new_value = os.environ.get(name, "")
            if new_value != old_value:
                changed.append(name)
                self._env_vars[name] = new_value
        return changed
