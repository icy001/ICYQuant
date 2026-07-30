"""
Release manifest generation for ICYQuant.

Creates comprehensive release manifests including version, build metadata,
Git commit information, dependencies, configuration hash, API schema
version, and infrastructure requirements. Validates manifest completeness.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class DependencyInfo:
    name: str
    version: str
    license: str = ""
    is_direct: bool = True
    optional: bool = False


@dataclass
class BuildMetadata:
    build_id: str
    build_number: int
    build_timestamp: str
    build_environment: str
    builder_name: str
    builder_version: str
    python_version: str
    platform_system: str
    platform_release: str


@dataclass
class InfrastructureRequirement:
    component: str
    min_version: str
    recommended_version: str
    purpose: str
    critical: bool = True


@dataclass
class ReleaseManifestResult:
    success: bool
    manifest_version: str
    manifest_hash: str
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    completeness_score: float = 0.0
    is_complete: bool = False

    @property
    def is_valid(self) -> bool:
        return self.success and self.is_complete and len(self.validation_errors) == 0


class ReleaseManifest:
    """
    Creates comprehensive release manifests for ICYQuant releases.

    Assembles version info, build metadata, Git commit, dependencies,
    configuration hashes, API schema versions, and infrastructure
    requirements into a validated release manifest.
    """

    MANIFEST_VERSION = "1.0.0"
    REQUIRED_FIELDS = [
        "version",
        "build_metadata",
        "git_commit",
        "api_schema_version",
        "config_hash",
    ]

    def __init__(
        self,
        version: str,
        *,
        git_commit: str = "",
        git_branch: str = "",
        api_schema_version: str = "1.0.0",
    ) -> None:
        self.version = version
        self.git_commit = git_commit
        self.git_branch = git_branch
        self.api_schema_version = api_schema_version
        self._dependencies: list[DependencyInfo] = []
        self._config_entries: dict[str, Any] = {}
        self._infra_requirements: list[InfrastructureRequirement] = []
        self._build_metadata: Optional[BuildMetadata] = None
        self._extra_metadata: dict[str, Any] = {}

    def add_dependency(
        self,
        name: str,
        version: str,
        *,
        license: str = "",
        is_direct: bool = True,
        optional: bool = False,
    ) -> None:
        self._dependencies.append(DependencyInfo(
            name=name,
            version=version,
            license=license,
            is_direct=is_direct,
            optional=optional,
        ))

    def add_config_entry(self, key: str, value: Any) -> None:
        self._config_entries[key] = value

    def add_infrastructure_requirement(
        self,
        component: str,
        min_version: str,
        recommended_version: str,
        purpose: str,
        *,
        critical: bool = True,
    ) -> None:
        self._infra_requirements.append(InfrastructureRequirement(
            component=component,
            min_version=min_version,
            recommended_version=recommended_version,
            purpose=purpose,
            critical=critical,
        ))

    def set_build_metadata(
        self,
        *,
        build_id: str = "",
        build_number: int = 0,
        build_environment: str = "local",
    ) -> None:
        self._build_metadata = BuildMetadata(
            build_id=build_id or self._generate_build_id(),
            build_number=build_number,
            build_timestamp=datetime.now(timezone.utc).isoformat(),
            build_environment=build_environment,
            builder_name="ICYQuant Builder",
            builder_version=self.version,
            python_version=platform.python_version(),
            platform_system=platform.system(),
            platform_release=platform.release(),
        )

    def set_extra_metadata(self, key: str, value: Any) -> None:
        self._extra_metadata[key] = value

    def generate(self) -> ReleaseManifestResult:
        manifest = self._build_manifest()
        manifest_json = json.dumps(
            manifest, indent=2, sort_keys=True, default=str
        )
        manifest_hash = self._compute_hash(manifest_json)

        errors: list[str] = []
        warnings: list[str] = []

        self._validate_manifest(manifest, errors, warnings)

        completeness = self._calculate_completeness(manifest)

        is_complete = completeness >= 0.8

        return ReleaseManifestResult(
            success=len(errors) == 0,
            manifest_version=self.MANIFEST_VERSION,
            manifest_hash=manifest_hash,
            validation_errors=errors,
            warnings=warnings,
            completeness_score=completeness,
            is_complete=is_complete,
        )

    def to_dict(self) -> dict[str, Any]:
        return self._build_manifest()

    def to_json(self, *, indent: int = 2) -> str:
        manifest = self._build_manifest()
        return json.dumps(manifest, indent=indent, sort_keys=True, default=str)

    def _build_manifest(self) -> dict[str, Any]:
        if self._build_metadata is None:
            self.set_build_metadata()

        config_hash = self._compute_config_hash()

        return {
            "manifest_version": self.MANIFEST_VERSION,
            "version": self.version,
            "api_schema_version": self.api_schema_version,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "build_metadata": {
                "build_id": self._build_metadata.build_id,
                "build_number": self._build_metadata.build_number,
                "build_timestamp": self._build_metadata.build_timestamp,
                "build_environment": self._build_metadata.build_environment,
                "builder": {
                    "name": self._build_metadata.builder_name,
                    "version": self._build_metadata.builder_version,
                },
                "runtime": {
                    "python_version": self._build_metadata.python_version,
                    "platform": self._build_metadata.platform_system,
                    "platform_release": self._build_metadata.platform_release,
                },
            },
            "dependencies": [
                {
                    "name": d.name,
                    "version": d.version,
                    "license": d.license,
                    "is_direct": d.is_direct,
                    "optional": d.optional,
                }
                for d in self._dependencies
            ],
            "config_hash": config_hash,
            "config_entries": self._config_entries,
            "infrastructure_requirements": [
                {
                    "component": infra.component,
                    "min_version": infra.min_version,
                    "recommended_version": infra.recommended_version,
                    "purpose": infra.purpose,
                    "critical": infra.critical,
                }
                for infra in self._infra_requirements
            ],
            "extra_metadata": self._extra_metadata,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _validate_manifest(
        self,
        manifest: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        for field_name in self.REQUIRED_FIELDS:
            value = manifest.get(field_name)
            if value is None or (isinstance(value, str) and not value):
                errors.append(f"Missing required field: {field_name}")

        if self.version and not self._is_valid_semver(self.version):
            warnings.append(
                f"Version '{self.version}' does not follow semver format"
            )

        if self.git_commit and len(self.git_commit) < 7:
            warnings.append(
                "Git commit hash is shorter than 7 characters"
            )

        if len(self._dependencies) == 0:
            warnings.append(
                "No dependencies declared in manifest"
            )

        if len(self._infra_requirements) == 0:
            warnings.append(
                "No infrastructure requirements declared"
            )

    def _calculate_completeness(self, manifest: dict[str, Any]) -> float:
        score = 0.0
        total_checks = 0

        total_checks += 1
        if manifest.get("version"):
            score += 1

        total_checks += 1
        if manifest.get("build_metadata"):
            score += 1

        total_checks += 1
        if manifest.get("git_commit"):
            score += 1

        total_checks += 1
        if manifest.get("dependencies") and len(manifest["dependencies"]) > 0:
            score += 1

        total_checks += 1
        if manifest.get("config_hash"):
            score += 1

        total_checks += 1
        if manifest.get("api_schema_version"):
            score += 1

        total_checks += 1
        if manifest.get("infrastructure_requirements") and len(
            manifest["infrastructure_requirements"]
        ) > 0:
            score += 1

        total_checks += 1
        if manifest.get("config_entries") and len(manifest["config_entries"]) > 0:
            score += 1

        return score / total_checks if total_checks > 0 else 0.0

    def _compute_config_hash(self) -> str:
        data = {
            "version": self.version,
            "api_schema_version": self.api_schema_version,
            "git_commit": self.git_commit,
            "config": self._config_entries,
            "dependencies": [
                {"name": d.name, "version": d.version}
                for d in self._dependencies
            ],
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_build_id(self) -> str:
        timestamp = int(time.time() * 1000)
        random_part = os.urandom(4).hex()
        return f"build-{timestamp}-{random_part}"

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        parts = version.split(".")
        if len(parts) != 3:
            return False
        try:
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False