"""Plugin installer for the loader subsystem.

Installs plugins from parsed manifests or ZIP archives. Performs
package verification, manifest validation, entrypoint checks, and
registers the resulting :class:`~infrastructure.plugins.models.Plugin`
with the :class:`~infrastructure.plugins.registry.PluginRegistry`.
"""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import PluginInstallError, PluginManifestError
from ..manifest import PluginManifest
from ..models import Plugin, PluginState
from ..registry import PluginRegistry
from .validator import LoaderValidator

logger = logging.getLogger(__name__)


class PluginInstaller:
    """Installs plugins from manifests or ZIP archives.

    The installer validates each plugin before registration and
    records installation metrics. It can install directly from a
    :class:`PluginManifest` or extract and install from a ZIP
    archive.

    Attributes:
        registry: The plugin registry to register installed plugins
            with.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None) -> None:
        self._registry = registry
        self._validator = LoaderValidator()
        self._install_count: int = 0
        self._failure_count: int = 0

    async def install(
        self,
        manifest: PluginManifest,
        plugin_dir: Optional[str] = None,
    ) -> Plugin:
        """Install a plugin from a parsed manifest.

        Validates the manifest, verifies the package, creates a
        :class:`Plugin` data object, and registers it with the
        plugin registry.

        Args:
            manifest: The plugin manifest describing the plugin
                to install.
            plugin_dir: Optional target directory. When provided,
                the manifest is written to ``<plugin_dir>/manifest.yaml``.

        Returns:
            The newly created :class:`Plugin` object.

        Raises:
            PluginManifestError: If the manifest fails validation.
            PluginInstallError: If the plugin cannot be registered.
        """
        if manifest is None:
            raise PluginManifestError("Manifest cannot be None")

        errors = await self.validate_manifest(manifest)
        if errors:
            self._failure_count += 1
            raise PluginManifestError(
                f"Manifest validation failed for '{manifest.id}': {'; '.join(errors)}"
            )

        if plugin_dir is not None:
            self._write_manifest(plugin_dir, manifest)

        plugin = await self.register_plugin(manifest)
        self._install_count += 1
        logger.info("Installed plugin '%s'.", manifest.id)
        return plugin

    async def install_from_zip(
        self,
        zip_path: str,
        extract_dir: Optional[str] = None,
    ) -> Plugin:
        """Install a plugin from a ZIP archive.

        Extracts the archive, locates the manifest file, validates
        it, and registers the plugin.

        Args:
            zip_path: Path to the ZIP archive.
            extract_dir: Optional extraction directory. When ``None``,
                a temporary directory is created.

        Returns:
            The newly created :class:`Plugin` object.

        Raises:
            PluginInstallError: If the ZIP is invalid, extraction
                fails, or no manifest is found.
        """
        if not zip_path:
            raise PluginInstallError("ZIP path cannot be empty")

        if not zipfile.is_zipfile(zip_path):
            raise PluginInstallError(f"Not a valid ZIP file: {zip_path}")

        target = extract_dir
        if target is None:
            target = self._create_temp_dir("icyquant_plugin_")

        try:
            extracted = await self.extract_package(zip_path, target)

            manifest_path = self._find_manifest(Path(extracted))
            if manifest_path is None:
                raise PluginInstallError(
                    f"No manifest found in extracted archive: {extracted}"
                )

            manifest = PluginManifest.from_yaml(str(manifest_path))
            plugin = await self.install(manifest, extracted)
            return plugin
        except Exception:
            if not extract_dir or extract_dir == target:
                shutil.rmtree(target, ignore_errors=True)
            raise

    async def verify_package(self, package_dir: str) -> List[str]:
        """Verify the integrity of an extracted plugin package.

        Checks that the directory exists, contains a valid manifest,
        and has a well-formed entrypoint.

        Args:
            package_dir: Path to the extracted plugin directory.

        Returns:
            A list of error messages; empty if the package is valid.
        """
        errors: List[str] = []

        if not package_dir:
            errors.append("Package directory cannot be empty")
            return errors

        pkg_path = Path(package_dir)
        if not pkg_path.exists() or not pkg_path.is_dir():
            errors.append(f"Package directory does not exist: {package_dir}")
            return errors

        manifest_path = self._find_manifest(pkg_path)
        if manifest_path is None:
            errors.append(f"No manifest file found in: {package_dir}")
            return errors

        try:
            manifest = PluginManifest.from_yaml(str(manifest_path))
        except Exception as exc:
            errors.append(f"Failed to parse manifest: {exc}")
            return errors

        manifest_errors = self._validator.validate_manifest(manifest)
        errors.extend(manifest_errors)

        entrypoint = manifest.entrypoint or ""
        entrypoint_errors = self._validator.validate_entrypoint(entrypoint)
        errors.extend(entrypoint_errors)

        return errors

    async def extract_package(
        self, zip_path: str, target_dir: str
    ) -> str:
        """Extract a ZIP archive to a target directory.

        Handles the common case where the archive contains a single
        top-level directory by returning that inner directory path.

        Args:
            zip_path: Path to the ZIP archive.
            target_dir: Directory to extract into.

        Returns:
            The resolved extracted directory path (which may be
            a sub-directory of *target_dir* if the archive has a
            single top-level entry).

        Raises:
            PluginInstallError: If extraction fails.
        """
        try:
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                zf.extractall(target_dir)

            top_levels: set = set()
            for name in names:
                top = name.split(os.path.sep, 1)[0]
                if top:
                    top_levels.add(top)

            extracted_dir = target_dir
            if len(top_levels) == 1:
                single = os.path.join(target_dir, top_levels.pop())
                if os.path.isdir(single):
                    extracted_dir = single

            logger.debug(
                "Extracted '%s' to '%s'.", zip_path, extracted_dir
            )
            return extracted_dir
        except zipfile.BadZipFile as exc:
            raise PluginInstallError(
                f"Invalid ZIP file '{zip_path}': {exc}"
            ) from exc
        except OSError as exc:
            raise PluginInstallError(
                f"Failed to extract '{zip_path}' to '{target_dir}': {exc}"
            ) from exc

    async def validate_manifest(self, manifest: PluginManifest) -> List[str]:
        """Validate a plugin manifest.

        Delegates to :class:`LoaderValidator` for structural checks
        and verifies the entrypoint format.

        Args:
            manifest: The manifest to validate.

        Returns:
            A list of error messages; empty if the manifest is valid.
        """
        if manifest is None:
            return ["Manifest is None"]

        errors = self._validator.validate_manifest(manifest)

        entrypoint = manifest.entrypoint or ""
        entrypoint_errors = self._validator.validate_entrypoint(entrypoint)
        errors.extend(entrypoint_errors)

        return errors

    async def register_plugin(self, manifest: PluginManifest) -> Plugin:
        """Create a :class:`Plugin` from a manifest and register it.

        Builds a :class:`Plugin` data object and registers it with
        the configured :class:`PluginRegistry` (if any).

        Args:
            manifest: The plugin manifest.

        Returns:
            The newly created :class:`Plugin` object.

        Raises:
            PluginInstallError: If plugin creation or registration fails.
        """
        try:
            plugin = Plugin(
                id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                author=manifest.author,
                description=manifest.description,
                entrypoint=manifest.entrypoint,
                api_version=manifest.api,
                state=PluginState.REGISTERED,
                capabilities=list(manifest.capabilities),
                permissions=list(manifest.permissions),
                dependencies=list(manifest.dependencies),
                config=dict(manifest.config),
                metadata=dict(manifest.metadata),
                installed_at=datetime.now(),
            )

            if self._registry is not None:
                self._registry.register(plugin.id, plugin)

            logger.info("Registered plugin '%s'.", plugin.id)
            return plugin
        except Exception as exc:
            logger.error(
                "Failed to register plugin '%s': %s",
                manifest.id,
                exc,
            )
            raise PluginInstallError(
                f"Failed to register plugin '{manifest.id}': {exc}"
            ) from exc

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the installer state to a dictionary.

        Returns:
            A dictionary with installation counts and registry info.
        """
        total = self._install_count + self._failure_count
        return {
            "install_count": self._install_count,
            "failure_count": self._failure_count,
            "total_attempts": total,
            "success_rate": (
                self._install_count / total if total > 0 else 0.0
            ),
            "has_registry": self._registry is not None,
        }

    @staticmethod
    def _create_temp_dir(prefix: str) -> str:
        """Create a temporary directory for plugin extraction."""
        import tempfile

        return tempfile.mkdtemp(prefix=prefix)

    @staticmethod
    def _write_manifest(plugin_dir: str, manifest: PluginManifest) -> None:
        """Write a manifest file to a plugin directory."""
        os.makedirs(plugin_dir, exist_ok=True)
        manifest_path = os.path.join(plugin_dir, "manifest.yaml")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.to_yaml())

    @staticmethod
    def _find_manifest(directory: Path) -> Optional[Path]:
        """Find a manifest file in a directory (non-recursive)."""
        for name in ("manifest.yaml", "manifest.yml"):
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None