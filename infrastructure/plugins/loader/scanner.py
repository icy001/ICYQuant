"""Directory scanner for the plugin loader subsystem.

Recursively scans directories for ``manifest.yaml`` (or
``manifest.yml``) files, parses them into
:class:`~infrastructure.plugins.manifest.PluginManifest` objects,
and reports duplicates, compatibility issues, and structural
validation results.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..manifest import PluginManifest

logger = logging.getLogger(__name__)

MANIFEST_FILENAMES = ("manifest.yaml", "manifest.yml")

PLUGIN_STRUCTURE_FILES = (
    "plugin.py",
    "config.yaml",
    "config.yml",
)

PLUGIN_STRUCTURE_DIRS = (
    "resources",
    "templates",
    "static",
)


class DirectoryScanner:
    """Scans directories for plugin manifests.

    Recursively walks a search path looking for manifest files,
    parses them into :class:`PluginManifest` objects, and provides
    utilities for duplicate detection, compatibility checking,
    and directory structure validation.
    """

    def __init__(self, max_depth: int = 5) -> None:
        self._max_depth = max_depth
        self._stats: Dict[str, int] = {
            "scans": 0,
            "manifests_found": 0,
            "duplicates_found": 0,
            "errors": 0,
        }

    def scan(self, plugin_dir: str) -> List[PluginManifest]:
        """Recursively scan a directory for plugin manifests.

        Args:
            plugin_dir: Root directory to scan.

        Returns:
            List of parsed :class:`PluginManifest` objects.
            Manifests that fail to parse are skipped with a
            warning logged.
        """
        p = Path(plugin_dir)
        if not p.exists() or not p.is_dir():
            logger.warning(
                "Scan path does not exist or is not a directory: %s",
                plugin_dir,
            )
            return []

        manifests: List[PluginManifest] = []
        self._scan_recursive(p, manifests, depth=0)

        self._stats["scans"] += 1
        self._stats["manifests_found"] += len(manifests)

        duplicates = self.detect_duplicates(manifests)
        if duplicates:
            self._stats["duplicates_found"] += len(duplicates)
            for dup_id in duplicates:
                logger.warning(
                    "Duplicate plugin id detected during scan: %s", dup_id
                )

        return manifests

    def discover_manifests(self, plugin_dir: str) -> List[Path]:
        """Find all manifest file paths under a directory.

        Args:
            plugin_dir: Root directory to search.

        Returns:
            Sorted list of :class:`~pathlib.Path` objects pointing
            to manifest files.
        """
        p = Path(plugin_dir)
        if not p.exists() or not p.is_dir():
            return []

        results: List[Path] = []
        self._find_manifests_recursive(p, results, depth=0)
        results.sort()
        return results

    def detect_duplicates(
        self, manifests: List[PluginManifest]
    ) -> List[str]:
        """Find duplicate plugin IDs across manifests.

        Args:
            manifests: List of manifests to check.

        Returns:
            Sorted list of plugin IDs that appear more than once.
        """
        counts: Dict[str, int] = {}
        for manifest in manifests:
            pid = manifest.id
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
        return sorted(pid for pid, count in counts.items() if count > 1)

    def check_compatibility(
        self,
        manifests: List[PluginManifest],
        api_version: str = "v1",
    ) -> List[PluginManifest]:
        """Filter manifests to those compatible with the given API version.

        Args:
            manifests: List of manifests to filter.
            api_version: Target API version (default ``"v1"``).

        Returns:
            List of compatible manifests.
        """
        return [m for m in manifests if m.is_compatible(api_version)]

    def get_plugin_structure(self, plugin_dir: str) -> Dict[str, Any]:
        """Return structural information about a plugin directory.

        Checks for the presence of common files (``plugin.py``,
        ``config.yaml``) and directories (``resources/``, etc.).

        Args:
            plugin_dir: Plugin directory to inspect.

        Returns:
            Dictionary with boolean flags for each structural
            element, plus a ``files`` list of all files found.
        """
        p = Path(plugin_dir)
        structure: Dict[str, Any] = {
            "path": str(p),
            "exists": p.exists(),
            "is_dir": p.is_dir(),
        }

        if not p.exists() or not p.is_dir():
            return structure

        structure["has_manifest"] = any(
            (p / name).is_file() for name in MANIFEST_FILENAMES
        )
        structure["has_plugin_py"] = (p / "plugin.py").is_file()
        structure["has_config_yaml"] = any(
            (p / name).is_file() for name in ("config.yaml", "config.yml")
        )
        structure["has_resources_dir"] = (p / "resources").is_dir()
        structure["has_templates_dir"] = (p / "templates").is_dir()
        structure["has_static_dir"] = (p / "static").is_dir()

        files: List[str] = []
        try:
            for item in p.iterdir():
                files.append(item.name)
        except OSError:
            pass
        structure["files"] = sorted(files)

        return structure

    def validate_plugin_directory(self, plugin_dir: str) -> List[str]:
        """Validate a plugin directory structure.

        Checks for the presence of a manifest file, a plugin entry
        point, and reports any issues found.

        Args:
            plugin_dir: Directory to validate.

        Returns:
            List of error messages. An empty list indicates a valid
            directory.
        """
        errors: List[str] = []
        p = Path(plugin_dir)

        if not p.exists():
            errors.append(f"Directory does not exist: {plugin_dir}")
            return errors

        if not p.is_dir():
            errors.append(f"Path is not a directory: {plugin_dir}")
            return errors

        manifests_found = [
            name for name in MANIFEST_FILENAMES if (p / name).is_file()
        ]
        if not manifests_found:
            errors.append(
                f"No manifest file found (looked for {MANIFEST_FILENAMES})"
            )
            return errors

        manifest_path = p / manifests_found[0]
        try:
            manifest = PluginManifest.from_yaml(str(manifest_path))
        except Exception as exc:
            errors.append(f"Failed to parse manifest: {exc}")
            return errors

        manifest_errors = manifest.validate()
        errors.extend(manifest_errors)

        if not manifest.entrypoint:
            errors.append(
                "Manifest is missing an entrypoint field"
            )

        if not self._has_entrypoint_module(p, manifest.entrypoint):
            errors.append(
                f"Entrypoint module '{manifest.entrypoint}' "
                f"not found in directory"
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Return scanner statistics as a dictionary."""
        return {
            "max_depth": self._max_depth,
            "stats": dict(self._stats),
        }

    def _scan_recursive(
        self, path: Path, manifests: List[PluginManifest], depth: int
    ) -> None:
        """Recursively scan a directory tree for manifest files.

        Args:
            path: Directory to scan.
            manifests: Accumulator list for parsed manifests.
            depth: Current recursion depth.
        """
        if depth > self._max_depth:
            return

        for entry in path.iterdir():
            if entry.is_dir():
                self._scan_recursive(entry, manifests, depth + 1)
            elif entry.is_file() and entry.name in MANIFEST_FILENAMES:
                try:
                    manifest = PluginManifest.from_yaml(str(entry))
                    manifests.append(manifest)
                except Exception as exc:
                    self._stats["errors"] += 1
                    logger.warning(
                        "Failed to parse manifest '%s': %s", entry, exc
                    )

    def _find_manifests_recursive(
        self, path: Path, results: List[Path], depth: int
    ) -> None:
        """Recursively find manifest file paths.

        Args:
            path: Directory to scan.
            results: Accumulator list for manifest paths.
            depth: Current recursion depth.
        """
        if depth > self._max_depth:
            return

        try:
            entries = list(path.iterdir())
        except OSError:
            return

        for entry in entries:
            if entry.is_dir():
                self._find_manifests_recursive(entry, results, depth + 1)
            elif entry.is_file() and entry.name in MANIFEST_FILENAMES:
                results.append(entry)

    @staticmethod
    def _has_entrypoint_module(plugin_dir: Path, entrypoint: str) -> bool:
        """Check whether the entrypoint module exists within the plugin dir.

        Handles both ``"module:Class"`` and plain ``"module"`` formats.
        """
        if not entrypoint:
            return False

        module_path = entrypoint
        if ":" in entrypoint:
            module_path = entrypoint.split(":", 1)[0]

        relative = module_path.replace(".", "/")
        candidate = plugin_dir / f"{relative}.py"
        if candidate.is_file():
            return True

        candidate_init = plugin_dir / relative / "__init__.py"
        if candidate_init.is_file():
            return True

        return False