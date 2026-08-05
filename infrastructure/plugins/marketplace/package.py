"""Package management for the plugin marketplace.

Provides :class:`MarketplacePackage` for creating, validating,
extracting, and inspecting plugin packages (ZIP archives
containing a manifest and plugin code).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..manifest import PluginManifest

logger = logging.getLogger(__name__)


class MarketplacePackage:
    """Creates and validates plugin packages (ZIP archives).

    A valid plugin package is a ZIP file containing at minimum:

    - ``manifest.yaml`` : The plugin manifest file.
    - One or more plugin source files.

    Usage::

        pkg = MarketplacePackage()
        path = pkg.create_package(manifest, "/path/to/source")
        info = pkg.get_package_info(path)
        valid = pkg.validate_package(path)
        manifest = pkg.read_manifest(path)
    """

    def __init__(self) -> None:
        self._create_count: int = 0
        self._validate_count: int = 0
        self._extract_count: int = 0
        self._read_count: int = 0

    def create_package(
        self, manifest: PluginManifest, source_dir: str
    ) -> str:
        """Create a .zip package from a plugin source directory.

        The manifest is written to ``manifest.yaml`` inside the
        archive, and all files from ``source_dir`` are included.

        Args:
            manifest: The plugin manifest describing the package.
            source_dir: Directory containing the plugin source files.

        Returns:
            The path to the created ZIP file.

        Raises:
            FileNotFoundError: If the source directory does not exist.
            OSError: If the package cannot be created.
        """
        if not os.path.isdir(source_dir):
            raise FileNotFoundError(
                f"Source directory not found: {source_dir}"
            )

        os.makedirs(source_dir, exist_ok=True)
        package_name = f"{manifest.id}-{manifest.version}.zip"
        package_dir = tempfile.mkdtemp(prefix="icyquant_pkg_")
        package_path = os.path.join(package_dir, package_name)

        try:
            with zipfile.ZipFile(
                package_path, "w", zipfile.ZIP_DEFLATED
            ) as zf:
                manifest_content = manifest.to_yaml()
                zf.writestr("manifest.yaml", manifest_content)

                source_path = Path(source_dir)
                for item in source_path.rglob("*"):
                    if item.is_file():
                        arcname = str(
                            item.relative_to(source_path)
                        )
                        zf.write(item, arcname)

            self._create_count += 1
            logger.info(
                "Created package '%s'.", package_path
            )
            return package_path
        except Exception:
            if os.path.exists(package_path):
                os.remove(package_path)
            raise

    def validate_package(
        self, package_path: str
    ) -> Dict[str, Any]:
        """Validate a plugin package's structure.

        Checks that the file is a valid ZIP, contains a manifest,
        and the manifest is well-formed.

        Args:
            package_path: Path to the .zip package file.

        Returns:
            A dictionary with ``valid`` (bool), ``errors`` (list),
            and ``warnings`` (list) keys.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not os.path.isfile(package_path):
            errors.append(f"Package file not found: {package_path}")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if not zipfile.is_zipfile(package_path):
            errors.append(f"Not a valid ZIP file: {package_path}")
            return {"valid": False, "errors": errors, "warnings": warnings}

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                names = zf.namelist()

                if not names:
                    errors.append("Package is empty.")
                    return {
                        "valid": False,
                        "errors": errors,
                        "warnings": warnings,
                    }

                manifest_found = any(
                    n.endswith("manifest.yaml")
                    or n.endswith("manifest.yml")
                    for n in names
                )
                if not manifest_found:
                    errors.append(
                        "No manifest.yaml found in package."
                    )

                if manifest_found:
                    manifest = self._extract_manifest_from_zip(zf)
                    if manifest is not None:
                        validation_errors = manifest.validate()
                        errors.extend(validation_errors)

                has_python_files = any(
                    n.endswith(".py") for n in names
                )
                if not has_python_files:
                    warnings.append(
                        "Package contains no Python files."
                    )
        except zipfile.BadZipFile as exc:
            errors.append(f"Corrupted ZIP file: {exc}")
        except Exception as exc:
            errors.append(f"Validation error: {exc}")

        self._validate_count += 1
        is_valid = len(errors) == 0
        logger.debug(
            "Package '%s' validation: valid=%s, errors=%d, warnings=%d.",
            package_path,
            is_valid,
            len(errors),
            len(warnings),
        )
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        }

    def extract_package(
        self, package_path: str, target_dir: str
    ) -> str:
        """Extract a plugin package to a target directory.

        Args:
            package_path: Path to the .zip package file.
            target_dir: Directory to extract into.

        Returns:
            The resolved extracted directory path.

        Raises:
            FileNotFoundError: If the package file does not exist.
            OSError: If extraction fails.
        """
        if not os.path.isfile(package_path):
            raise FileNotFoundError(
                f"Package file not found: {package_path}"
            )

        try:
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(package_path, "r") as zf:
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

            self._extract_count += 1
            logger.info(
                "Extracted '%s' to '%s'.",
                package_path,
                extracted_dir,
            )
            return extracted_dir
        except zipfile.BadZipFile as exc:
            raise OSError(
                f"Invalid ZIP file '{package_path}': {exc}"
            ) from exc

    def read_manifest(
        self, package_path: str
    ) -> Optional[PluginManifest]:
        """Read the manifest from a plugin package without extracting.

        Args:
            package_path: Path to the .zip package file.

        Returns:
            The parsed :class:`PluginManifest`, or ``None`` if
            the manifest cannot be found or parsed.
        """
        if not os.path.isfile(package_path):
            return None

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                manifest = self._extract_manifest_from_zip(zf)
            self._read_count += 1
            return manifest
        except Exception as exc:
            logger.warning(
                "Failed to read manifest from '%s': %s",
                package_path,
                exc,
            )
            return None

    def get_package_info(
        self, package_path: str
    ) -> Dict[str, Any]:
        """Get detailed information about a plugin package.

        Args:
            package_path: Path to the .zip package file.

        Returns:
            A dictionary with package metadata including
            ``size``, ``file_count``, ``manifest``, and
            validation results.
        """
        info: Dict[str, Any] = {
            "path": package_path,
            "exists": os.path.isfile(package_path),
        }

        if not info["exists"]:
            return info

        try:
            stat = os.stat(package_path)
            info["size_bytes"] = stat.st_size
            info["modified_at"] = stat.st_mtime

            if zipfile.is_zipfile(package_path):
                with zipfile.ZipFile(package_path, "r") as zf:
                    names = zf.namelist()
                    info["file_count"] = len(names)
                    info["compressed_size"] = sum(
                        zi.compress_size for zi in zf.infolist()
                    )
                    manifest = self._extract_manifest_from_zip(zf)
                    if manifest is not None:
                        info["manifest"] = manifest.to_dict()

            validation = self.validate_package(package_path)
            info["validation"] = validation

        except Exception as exc:
            info["error"] = str(exc)

        return info

    def list_package_contents(
        self, package_path: str
    ) -> List[str]:
        """List all files contained in a plugin package.

        Args:
            package_path: Path to the .zip package file.

        Returns:
            A list of file paths inside the archive.
        """
        if not os.path.isfile(package_path):
            return []

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                return zf.namelist()
        except Exception:
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Return package management statistics.

        Returns:
            Dictionary with operation counts.
        """
        return {
            "create_count": self._create_count,
            "validate_count": self._validate_count,
            "extract_count": self._extract_count,
            "read_count": self._read_count,
        }

    @staticmethod
    def _extract_manifest_from_zip(
        zf: zipfile.ZipFile,
    ) -> Optional[PluginManifest]:
        """Extract and parse the manifest from an open ZIP file.

        Args:
            zf: An open ZipFile handle.

        Returns:
            The parsed :class:`PluginManifest`, or ``None``.
        """
        for name in zf.namelist():
            if name.endswith("manifest.yaml") or name.endswith(
                "manifest.yml"
            ):
                try:
                    content = zf.read(name).decode("utf-8")
                    return PluginManifest.from_yaml_string(content)
                except Exception:
                    continue
        return None