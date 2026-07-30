"""
SBOM (Software Bill of Materials) generator for ICYQuant.

Generates SBOMs in CycloneDX and SPDX formats by scanning Python packages,
system libraries, Docker base image info, and third-party components.
Includes license information, version constraints, and known
vulnerability references.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class PackageInfo:
    name: str
    version: str
    ecosystem: str
    license: str = ""
    is_direct: bool = True
    description: str = ""
    homepage: str = ""
    vulnerabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LicenseInfo:
    spdx_id: str
    name: str
    is_compliant: bool = True


@dataclass
class SBOMResult:
    success: bool
    total_packages: int = 0
    direct_packages: int = 0
    transitive_packages: int = 0
    license_compliant: bool = True
    license_issues: list[str] = field(default_factory=list)
    vulnerability_count: int = 0
    critical_vulnerabilities: int = 0
    high_vulnerabilities: int = 0
    output_files: list[str] = field(default_factory=list)
    generated_at: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def has_vulnerabilities(self) -> bool:
        return self.vulnerability_count > 0

    @property
    def risk_level(self) -> str:
        if self.critical_vulnerabilities > 0:
            return "critical"
        if self.high_vulnerabilities > 0:
            return "high"
        if self.vulnerability_count > 0:
            return "medium"
        return "low"


class SBOMGenerator:
    """
    Generates Software Bill of Materials for ICYQuant releases.

    Scans Python packages, system libraries, and third-party components
    to produce comprehensive SBOMs in both CycloneDX and SPDX formats.
    """

    SPDX_VERSION = "2.3"
    CYCLONEDX_VERSION = "1.5"
    ECOSYSTEM_PYTHON = "pypi"
    ECOSYSTEM_SYSTEM = "system"
    ECOSYSTEM_DOCKER = "docker"

    def __init__(
        self,
        project_name: str = "ICYQuant",
        project_version: str = "0.3.0",
    ) -> None:
        self.project_name = project_name
        self.project_version = project_version
        self._packages: list[PackageInfo] = []
        self._docker_base_image: str = ""
        self._system_libraries: list[str] = []
        self._compliance_licenses: set[str] = {
            "MIT",
            "Apache-2.0",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "ISC",
            "MPL-2.0",
            "LGPL-2.1-only",
            "GPL-2.0-only",
        }
        self._known_vulnerabilities: dict[str, list[str]] = {}

    def scan_python_packages(self) -> list[PackageInfo]:
        packages: list[PackageInfo] = []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return packages

            pip_list = json.loads(result.stdout)
            for pkg in pip_list:
                name = pkg.get("name", "")
                version = pkg.get("version", "")
                if name and name != "pip":
                    pkg_info = PackageInfo(
                        name=name,
                        version=version,
                        ecosystem=self.ECOSYSTEM_PYTHON,
                        is_direct=True,
                    )
                    packages.append(pkg_info)
                    self._packages.append(pkg_info)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass
        return packages

    def add_package(
        self,
        name: str,
        version: str,
        *,
        ecosystem: str = "pypi",
        license: str = "",
        is_direct: bool = True,
        description: str = "",
        homepage: str = "",
        vulnerabilities: Optional[list[str]] = None,
    ) -> None:
        pkg = PackageInfo(
            name=name,
            version=version,
            ecosystem=ecosystem,
            license=license,
            is_direct=is_direct,
            description=description,
            homepage=homepage,
            vulnerabilities=vulnerabilities or [],
        )
        self._packages.append(pkg)

    def set_docker_base_image(self, image: str) -> None:
        self._docker_base_image = image
        pkg = PackageInfo(
            name=image.split(":")[0] if ":" in image else image,
            version=image.split(":")[1] if ":" in image else "latest",
            ecosystem=self.ECOSYSTEM_DOCKER,
            description=f"Docker base image: {image}",
            is_direct=False,
        )
        self._packages.append(pkg)

    def add_system_library(
        self, name: str, version: str, *, description: str = ""
    ) -> None:
        self._system_libraries.append(f"{name}=={version}")
        pkg = PackageInfo(
            name=name,
            version=version,
            ecosystem=self.ECOSYSTEM_SYSTEM,
            description=description or name,
            is_direct=False,
        )
        self._packages.append(pkg)

    def add_known_vulnerability(
        self, package_name: str, cve_ids: list[str]
    ) -> None:
        self._known_vulnerabilities[package_name] = cve_ids

    def set_compliance_licenses(self, licenses: set[str]) -> None:
        self._compliance_licenses = licenses

    def generate(
        self, output_dir: str = "release/sbom"
    ) -> SBOMResult:
        errors: list[str] = []
        output_files: list[str] = []

        self._apply_known_vulnerabilities()

        try:
            cyclonedx_path = self._generate_cyclonedx(output_dir)
            output_files.append(cyclonedx_path)
        except Exception as e:
            errors.append(f"CycloneDX generation failed: {e}")

        try:
            spdx_path = self._generate_spdx(output_dir)
            output_files.append(spdx_path)
        except Exception as e:
            errors.append(f"SPDX generation failed: {e}")

        license_issues = self._check_license_compliance()
        vuln_count, critical, high = self._count_vulnerabilities()

        direct = sum(1 for p in self._packages if p.is_direct)
        transitive = len(self._packages) - direct

        success = len(errors) == 0
        return SBOMResult(
            success=success,
            total_packages=len(self._packages),
            direct_packages=direct,
            transitive_packages=transitive,
            license_compliant=len(license_issues) == 0,
            license_issues=license_issues,
            vulnerability_count=vuln_count,
            critical_vulnerabilities=critical,
            high_vulnerabilities=high,
            output_files=output_files,
            generated_at=datetime.now(timezone.utc).isoformat(),
            errors=errors,
        )

    def _apply_known_vulnerabilities(self) -> None:
        for pkg in self._packages:
            cve_ids = self._known_vulnerabilities.get(pkg.name, [])
            if cve_ids:
                pkg.vulnerabilities.extend(cve_ids)

    def _check_license_compliance(self) -> list[str]:
        issues: list[str] = []
        for pkg in self._packages:
            if pkg.license and pkg.license not in self._compliance_licenses:
                issues.append(
                    f"Package '{pkg.name}' ({pkg.version}) uses "
                    f"non-compliant license: {pkg.license}"
                )
        return issues

    def _count_vulnerabilities(self) -> tuple[int, int, int]:
        total = 0
        critical = 0
        high = 0
        for pkg in self._packages:
            for cve in pkg.vulnerabilities:
                total += 1
                if "CRITICAL" in cve.upper():
                    critical += 1
                elif "HIGH" in cve.upper():
                    high += 1
        return total, critical, high

    def _generate_cyclonedx(self, output_dir: str) -> str:
        import os

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "cyclonedx-sbom.json")

        components = []
        for pkg in self._packages:
            component: dict[str, Any] = {
                "type": "library",
                "bom-ref": f"{pkg.name}@{pkg.version}",
                "name": pkg.name,
                "version": pkg.version,
                "purl": self._make_purl(pkg),
            }
            if pkg.description:
                component["description"] = pkg.description
            if pkg.license:
                component["licenses"] = [
                    {"license": {"id": pkg.license}}
                ]
            if pkg.vulnerabilities:
                component["properties"] = [
                    {
                        "name": "vulnerabilities",
                        "value": ", ".join(pkg.vulnerabilities),
                    }
                ]
            if not pkg.is_direct:
                component["scope"] = "optional"
            components.append(component)

        cyclonedx = {
            "bomFormat": "CycloneDX",
            "specVersion": self.CYCLONEDX_VERSION,
            "serialNumber": self._generate_serial(),
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tools": [
                    {
                        "vendor": "ICYQuant",
                        "name": "SBOMGenerator",
                        "version": self.project_version,
                    }
                ],
                "component": {
                    "type": "application",
                    "bom-ref": f"{self.project_name}@{self.project_version}",
                    "name": self.project_name,
                    "version": self.project_version,
                },
            },
            "components": components,
            "dependencies": [
                {
                    "ref": f"{self.project_name}@{self.project_version}",
                    "dependsOn": [
                        f"{p.name}@{p.version}"
                        for p in self._packages
                        if p.is_direct
                    ],
                }
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cyclonedx, f, indent=2, ensure_ascii=False)

        return filepath

    def _generate_spdx(self, output_dir: str) -> str:
        import os

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "spdx-sbom.json")

        packages = []
        relationships = []

        for pkg in self._packages:
            spdx_pkg: dict[str, Any] = {
                "SPDXID": f"SPDXRef-Package-{self._sanitize_id(pkg.name)}",
                "name": pkg.name,
                "versionInfo": pkg.version,
                "downloadLocation": pkg.homepage or "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": pkg.license or "NOASSERTION",
                "licenseDeclared": pkg.license or "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
            if pkg.description:
                spdx_pkg["description"] = pkg.description
            if pkg.vulnerabilities:
                spdx_pkg["externalRefs"] = [
                    {
                        "referenceCategory": "SECURITY",
                        "referenceType": "advisory",
                        "referenceLocator": cve,
                    }
                    for cve in pkg.vulnerabilities
                ]
            packages.append(spdx_pkg)

            relationships.append({
                "spdxElementId": "SPDXRef-ROOT",
                "relatedSpdxElement": spdx_pkg["SPDXID"],
                "relationshipType": "DEPENDS_ON",
            })

        spdx = {
            "spdxVersion": self.SPDX_VERSION,
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"{self.project_name}-{self.project_version}",
            "documentNamespace": (
                f"https://icyquant.io/spdx/{self.project_name}"
                f"/{self.project_version}"
            ),
            "creationInfo": {
                "created": datetime.now(timezone.utc).isoformat(),
                "creators": [
                    "Tool: ICYQuant-SBOMGenerator",
                    f"Project: {self.project_name}@{self.project_version}",
                ],
                "licenseListVersion": "3.19",
            },
            "packages": [
                {
                    "SPDXID": "SPDXRef-ROOT",
                    "name": self.project_name,
                    "versionInfo": self.project_version,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "licenseConcluded": "NOASSERTION",
                    "licenseDeclared": "NOASSERTION",
                    "copyrightText": "NOASSERTION",
                },
                *packages,
            ],
            "relationships": [
                {
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "relatedSpdxElement": "SPDXRef-ROOT",
                    "relationshipType": "DESCRIBES",
                },
                *relationships,
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(spdx, f, indent=2, ensure_ascii=False)

        return filepath

    def _make_purl(self, pkg: PackageInfo) -> str:
        if pkg.ecosystem == self.ECOSYSTEM_PYTHON:
            return f"pkg:pypi/{pkg.name}@{pkg.version}"
        elif pkg.ecosystem == self.ECOSYSTEM_DOCKER:
            return f"pkg:docker/{pkg.name}@{pkg.version}"
        elif pkg.ecosystem == self.ECOSYSTEM_SYSTEM:
            return f"pkg:system/{pkg.name}@{pkg.version}"
        return f"pkg:generic/{pkg.name}@{pkg.version}"

    def _generate_serial(self) -> str:
        import uuid
        return str(uuid.uuid4())

    @staticmethod
    def _sanitize_id(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9.-]", "-", name)