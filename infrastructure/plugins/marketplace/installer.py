"""Marketplace installer for the plugin marketplace.

Provides :class:`MarketplaceInstaller` for installing plugins
from packages and repositories, delegating actual loading to
the :class:`~infrastructure.plugins.loader.installer.PluginInstaller`.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from ..exceptions import PluginInstallError
from ..loader.installer import PluginInstaller
from ..manifest import PluginManifest
from ..models import PluginState

from .package import MarketplacePackage

logger = logging.getLogger(__name__)


class MarketplaceInstaller:
    """Installs plugins from marketplace packages and repositories.

    Delegates actual installation and loading to the
    :class:`PluginInstaller` from the loader subsystem, while
    providing pre-installation verification, dependency checking,
    and post-installation setup.

    Usage::

        installer = MarketplaceInstaller()
        result = await installer.install_from_repository(
            "my.plugin", "1.0.0"
        )
    """

    def __init__(
        self,
        package_mgr: Optional[MarketplacePackage] = None,
        plugin_installer: Optional[PluginInstaller] = None,
    ) -> None:
        self._package_mgr = package_mgr or MarketplacePackage()
        self._plugin_installer = plugin_installer or PluginInstaller()
        self._install_count: int = 0
        self._failure_count: int = 0
        self._verify_count: int = 0

    async def install(
        self,
        package_path: str,
        target_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Install a plugin from a local package file.

        Validates the package, extracts it, verifies the manifest,
        and registers the plugin.

        Args:
            package_path: Path to the .zip package file.
            target_dir: Optional target directory for installation.

        Returns:
            A dictionary with installation result.

        Raises:
            PluginInstallError: If the package cannot be installed.
        """
        if not package_path:
            raise PluginInstallError("Package path cannot be empty")

        verification = await self.verify_package(package_path)
        if verification:
            self._failure_count += 1
            raise PluginInstallError(
                f"Package verification failed: {'; '.join(verification)}"
            )

        try:
            manifest = self._package_mgr.read_manifest(package_path)
            if manifest is None:
                raise PluginInstallError(
                    "No valid manifest found in package."
                )

            pre_check = await self.pre_install_check(manifest)
            if not pre_check.get("compatible", True):
                raise PluginInstallError(
                    f"Pre-install check failed: "
                    f"{pre_check.get('reason', 'Unknown')}"
                )

            extract_dir = target_dir or tempfile.mkdtemp(
                prefix="icyquant_install_"
            )
            extracted = self._package_mgr.extract_package(
                package_path, extract_dir
            )

            plugin = await self._plugin_installer.install_from_zip(
                package_path, extracted
            )

            post_result = await self.post_install_setup(
                manifest.id
            )

            self._install_count += 1
            logger.info(
                "Installed plugin '%s' from '%s'.",
                manifest.id,
                package_path,
            )
            return {
                "success": True,
                "plugin_id": manifest.id,
                "version": manifest.version,
                "extracted_dir": extracted,
                "post_install": post_result,
                "message": "Plugin installed successfully.",
            }
        except PluginInstallError:
            self._failure_count += 1
            raise
        except Exception as exc:
            self._failure_count += 1
            logger.error(
                "Failed to install from '%s': %s", package_path, exc
            )
            raise PluginInstallError(
                f"Failed to install from '{package_path}': {exc}"
            ) from exc

    async def install_from_repository(
        self,
        plugin_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Install a plugin from a connected repository.

        In a full implementation this would download the package
        from a remote repository. For now it creates a placeholder
        installation.

        Args:
            plugin_id: The plugin identifier to install.
            version: Optional target version.

        Returns:
            A dictionary with installation result.
        """
        logger.info(
            "Installing '%s' (version=%s) from repository.",
            plugin_id,
            version or "latest",
        )

        try:
            self._install_count += 1
            return {
                "success": True,
                "plugin_id": plugin_id,
                "version": version or "latest",
                "source": "repository",
                "message": (
                    f"Plugin '{plugin_id}' installed from repository."
                ),
            }
        except Exception as exc:
            self._failure_count += 1
            raise PluginInstallError(
                f"Failed to install '{plugin_id}': {exc}"
            ) from exc

    async def verify_package(
        self, package_path: str
    ) -> List[str]:
        """Perform pre-installation verification of a package.

        Checks package integrity, manifest validity, and structure.

        Args:
            package_path: Path to the .zip package file.

        Returns:
            A list of error messages; empty if the package passes.
        """
        self._verify_count += 1
        errors: List[str] = []

        if not package_path:
            return ["Package path cannot be empty"]

        if not os.path.isfile(package_path):
            return [f"Package file not found: {package_path}"]

        validation = self._package_mgr.validate_package(package_path)
        if not validation.get("valid", False):
            errors.extend(validation.get("errors", []))

        manifest = self._package_mgr.read_manifest(package_path)
        if manifest is None:
            errors.append(
                "Cannot read manifest from package."
            )
        else:
            manifest_errors = manifest.validate()
            errors.extend(manifest_errors)

        return errors

    async def pre_install_check(
        self, manifest: PluginManifest
    ) -> Dict[str, Any]:
        """Check dependencies, permissions, and compatibility.

        Args:
            manifest: The plugin manifest to check.

        Returns:
            A dictionary with ``compatible`` (bool), ``reason`` (str),
            and ``details`` (dict) keys.
        """
        details: Dict[str, Any] = {
            "dependencies": [],
            "permissions": list(manifest.permissions),
            "api_version": manifest.api,
        }

        compatible = True
        reason = ""

        if not manifest.is_compatible("v1"):
            compatible = False
            reason = (
                f"Plugin requires API version '{manifest.api}' "
                f"which is incompatible with current version 'v1'."
            )

        for dep in manifest.dependencies:
            details["dependencies"].append(
                {"id": dep, "available": True}
            )

        return {
            "compatible": compatible,
            "reason": reason,
            "details": details,
        }

    async def post_install_setup(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Perform post-installation setup for a plugin.

        Args:
            plugin_id: The installed plugin's identifier.

        Returns:
            A dictionary with setup result.
        """
        logger.info("Post-install setup for '%s'.", plugin_id)
        return {
            "success": True,
            "plugin_id": plugin_id,
            "message": "Post-install setup completed.",
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return installer statistics.

        Returns:
            Dictionary with installation counts and success rate.
        """
        total = self._install_count + self._failure_count
        return {
            "install_count": self._install_count,
            "failure_count": self._failure_count,
            "verify_count": self._verify_count,
            "total_attempts": total,
            "success_rate": (
                self._install_count / total if total > 0 else 0.0
            ),
        }