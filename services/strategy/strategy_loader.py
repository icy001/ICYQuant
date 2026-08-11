"""
Production strategy loader.

Loads strategy packages from multiple sources (local, git, artifact
repository, remote registry) and resolves their dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .strategy_manifest import StrategyManifest
from .strategy_package import PackageFormat, PackageSource, StrategyPackage

logger = logging.getLogger(__name__)


class StrategyLoader:
    """Loads and resolves strategy packages from various sources.

    Supports:
        - Local directory/file loading
        - Git repository checkout
        - Artifact repository download
        - Remote registry fetching
    """

    def __init__(self) -> None:
        self._loaded_packages: Dict[str, StrategyPackage] = {}
        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyLoader initialized")

    async def shutdown(self) -> None:
        self._loaded_packages.clear()
        self._initialized = False
        logger.info("StrategyLoader shut down")

    # ── Loading ──

    async def load(
        self,
        source: PackageSource,
        manifest_overrides: Optional[Dict[str, Any]] = None,
    ) -> StrategyPackage:
        """Load a strategy package from the given source.

        Args:
            source: The package source specification.
            manifest_overrides: Optional manifest field overrides.

        Returns:
            A loaded StrategyPackage.

        Raises:
            ValueError: If the package cannot be loaded.
        """
        if source.format == PackageFormat.LOCAL:
            package = await self._load_local(source)
        elif source.format == PackageFormat.GIT:
            package = await self._load_git(source)
        elif source.format == PackageFormat.ARTIFACT:
            package = await self._load_artifact(source)
        elif source.format == PackageFormat.REMOTE_REGISTRY:
            package = await self._load_remote(source)
        else:
            raise ValueError(f"Unsupported package format: {source.format}")

        if manifest_overrides:
            package.manifest = StrategyManifest.from_dict({
                **package.manifest.to_dict(),
                **manifest_overrides,
            })

        package.mark_loaded()
        self._loaded_packages[package.package_id] = package
        logger.info("Loaded package: %s", package.package_id)
        return package

    async def load_from_manifest(
        self,
        manifest: StrategyManifest,
        source: Optional[PackageSource] = None,
    ) -> StrategyPackage:
        """Create a package instance directly from a manifest."""
        package = StrategyPackage(manifest=manifest, source=source)
        package.mark_loaded()
        self._loaded_packages[package.package_id] = package
        return package

    async def load_batch(
        self,
        sources: List[PackageSource],
    ) -> List[StrategyPackage]:
        """Load multiple packages."""
        packages: List[StrategyPackage] = []
        for source in sources:
            try:
                package = await self.load(source)
                packages.append(package)
            except Exception as e:
                logger.error("Failed to load package from %s: %s", source.location, e)
        return packages

    # ── Private Loaders ──

    async def _load_local(self, source: PackageSource) -> StrategyPackage:
        """Load a strategy from the local filesystem."""
        import json
        import os

        manifest_path = os.path.join(source.location, "manifest.json")
        if not os.path.exists(manifest_path):
            raise ValueError(f"manifest.json not found at {source.location}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        manifest = StrategyManifest.from_dict(manifest_data)
        return StrategyPackage(manifest=manifest, source=source)

    async def _load_git(self, source: PackageSource) -> StrategyPackage:
        """Load a strategy from a git repository."""
        logger.warning(
            "Git loading is not fully implemented. Using stub for %s",
            source.location,
        )
        manifest = StrategyManifest.from_dict({
            "name": source.metadata.get("name", "unknown"),
            "version": source.metadata.get("version", "0.1.0"),
            "entry_point": {"module": source.metadata.get("module", "")},
        })
        return StrategyPackage(manifest=manifest, source=source)

    async def _load_artifact(self, source: PackageSource) -> StrategyPackage:
        """Load a strategy from an artifact repository."""
        logger.warning(
            "Artifact loading is not fully implemented. Using stub for %s",
            source.location,
        )
        manifest = StrategyManifest.from_dict({
            "name": source.metadata.get("name", "unknown"),
            "version": source.metadata.get("version", "0.1.0"),
            "entry_point": {"module": source.metadata.get("module", "")},
        })
        return StrategyPackage(manifest=manifest, source=source)

    async def _load_remote(self, source: PackageSource) -> StrategyPackage:
        """Load a strategy from a remote registry."""
        logger.warning(
            "Remote registry loading is not fully implemented. Using stub for %s",
            source.location,
        )
        manifest = StrategyManifest.from_dict({
            "name": source.metadata.get("name", "unknown"),
            "version": source.metadata.get("version", "0.1.0"),
            "entry_point": {"module": source.metadata.get("module", "")},
        })
        return StrategyPackage(manifest=manifest, source=source)

    # ── Lookup ──

    def get_loaded(self, package_id: str) -> Optional[StrategyPackage]:
        return self._loaded_packages.get(package_id)

    def list_loaded(self) -> List[str]:
        return list(self._loaded_packages.keys())

    @property
    def loaded_count(self) -> int:
        return len(self._loaded_packages)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "loaded_packages": self.loaded_count,
            "initialized": self._initialized,
        }
