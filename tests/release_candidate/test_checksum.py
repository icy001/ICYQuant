"""
Tests for checksum generation, validation, and format compliance.

Covers:
- Checksum file existence and format
- SHA256 checksum algorithm usage
- Checksum coverage for all artifacts
- Checksum reproducibility
- Checksum validation against stored values
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_ARTIFACTS_DIR = PROJECT_ROOT / "release" / "artifacts"
RELEASE_RC_DIR = PROJECT_ROOT / "release" / "rc"


@pytest.fixture
def checksums_file():
    checksums_path = RELEASE_ARTIFACTS_DIR / "checksums.txt"
    if not checksums_path.exists():
        pytest.skip("checksums.txt not found")
    with open(checksums_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def signature_json():
    sig_path = RELEASE_RC_DIR / "release_signature.json"
    if not sig_path.exists():
        pytest.skip("release_signature.json not found")
    with open(sig_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class TestChecksumFile:
    """Tests for checksum file structure and content."""

    def test_checksums_file_exists(self):
        checksums = RELEASE_ARTIFACTS_DIR / "checksums.txt"
        assert checksums.exists(), "checksums.txt must exist in release/artifacts/"

    def test_checksums_file_has_header(self, checksums_file: str):
        assert "ICYQuant" in checksums_file
        assert "v0.4.0-alpha1-rc1" in checksums_file

    def test_checksums_use_sha256(self, checksums_file: str):
        assert "SHA256" in checksums_file

    def test_checksums_cover_docker_image(self, checksums_file: str):
        docker_terms = ["docker", "Docker", "image", ".docker"]
        found = any(term.lower() in checksums_file.lower() for term in docker_terms)
        assert found, "Checksums must cover Docker image"

    def test_checksums_cover_helm_chart(self, checksums_file: str):
        helm_terms = ["helm", "Helm", ".tgz"]
        found = any(term.lower() in checksums_file.lower() for term in helm_terms)
        assert found, "Checksums must cover Helm chart"

    def test_checksums_cover_sdk(self, checksums_file: str):
        sdk_terms = ["sdk", "SDK", ".whl", "wheel"]
        found = any(term in checksums_file for term in sdk_terms)
        assert found, "Checksums must cover SDK wheel"

    def test_checksums_cover_sbom(self, checksums_file: str):
        assert "sbom.json" in checksums_file, "Checksums must cover SBOM"

    def test_checksums_cover_provenance(self, checksums_file: str):
        assert "provenance.json" in checksums_file, "Checksums must cover provenance"

    def test_checksums_cover_openapi(self, checksums_file: str):
        assert "openapi" in checksums_file.lower(), "Checksums must cover OpenAPI spec"

    def test_checksums_cover_cli(self, checksums_file: str):
        cli_terms = ["cli", "CLI"]
        found = any(term in checksums_file for term in cli_terms)
        assert found, "Checksums must cover CLI binaries"

    def test_checksums_format_is_consistent(self, checksums_file: str):
        lines = checksums_file.strip().split("\n")
        hash_lines = [l for l in lines if l.startswith("SHA256")]
        for line in hash_lines:
            assert "=" in line, f"Checksum line must use = separator: {line}"

    def test_checksums_has_generated_timestamp(self, checksums_file: str):
        assert "Generated" in checksums_file or "生成" in checksums_file


class TestChecksumGeneration:
    """Tests for checksum generation logic."""

    def test_compute_sha256_produces_consistent_results(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, ICYQuant!")
        hash1 = compute_sha256(test_file)
        hash2 = compute_sha256(test_file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    def test_compute_sha256_different_content(self, tmp_path: Path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")
        assert compute_sha256(file1) != compute_sha256(file2)

    def test_compute_sha256_empty_file(self, tmp_path: Path):
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        hash_val = compute_sha256(test_file)
        assert len(hash_val) == 64

    def test_compute_sha256_large_file(self, tmp_path: Path):
        test_file = tmp_path / "large.bin"
        test_file.write_bytes(os.urandom(10000))
        hash_val = compute_sha256(test_file)
        assert len(hash_val) == 64


class TestChecksumValidation:
    """Tests for validating checksums against stored values."""

    def test_signature_checksums_format(self, signature_json: Dict):
        checksums = signature_json.get("checksums", {})
        for artifact, checksum in checksums.items():
            assert checksum.startswith("sha256:"), (
                f"Checksum for {artifact} must start with sha256:"
            )
            hash_part = checksum.replace("sha256:", "")
            assert len(hash_part) >= 60, (
                f"Checksum hash for {artifact} must be at least 60 hex chars"
            )
            assert all(c in "0123456789abcdef" for c in hash_part), (
                f"Checksum hash for {artifact} must be hexadecimal"
            )

    def test_all_artifacts_have_checksums(self, signature_json: Dict):
        checksums = signature_json.get("checksums", {})
        expected = ["docker_image", "helm_chart", "sdk_wheel", "kubernetes_manifests", "sbom"]
        for artifact in expected:
            assert artifact in checksums, f"Missing checksum for: {artifact}"

    def test_checksums_match_between_files(self, signature_json: Dict, checksums_file: str):
        sig_checksums = signature_json.get("checksums", {})
        for artifact, checksum in sig_checksums.items():
            hash_value = checksum.replace("sha256:", "")
            artifact_label = artifact.replace("_", " ")
            found_hash = hash_value in checksums_file
            found_label = artifact_label.lower() in checksums_file.lower()
            if not found_hash and not found_label:
                pytest.fail(
                    f"Checksum or artifact name for {artifact} not found in checksums.txt"
                )


class TestReleaseTagChecksumGeneration:
    """Tests for ReleaseTagGenerator checksum functionality."""

    def test_generate_checksums_returns_dict(self, tmp_path: Path):
        from release.rc.release_tag import ReleaseTagGenerator

        gen = ReleaseTagGenerator(version="0.4.0-alpha1")
        result = gen.generate_checksums(str(tmp_path))
        assert isinstance(result, dict)

    def test_generate_checksums_for_empty_dir(self, tmp_path: Path):
        from release.rc.release_tag import ReleaseTagGenerator

        gen = ReleaseTagGenerator(version="0.4.0-alpha1")
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = gen.generate_checksums(str(empty_dir))
        assert result == {}

    def test_generate_checksums_for_nonexistent_dir(self, tmp_path: Path):
        from release.rc.release_tag import ReleaseTagGenerator

        gen = ReleaseTagGenerator(version="0.4.0-alpha1")
        result = gen.generate_checksums(str(tmp_path / "nonexistent"))
        assert result == {}

    def test_generate_checksums_for_real_files(self, tmp_path: Path):
        from release.rc.release_tag import ReleaseTagGenerator

        test_dir = tmp_path / "artifacts"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("Content 1")
        (test_dir / "file2.txt").write_text("Content 2")

        gen = ReleaseTagGenerator(version="0.4.0-alpha1")
        result = gen.generate_checksums(str(test_dir))
        assert len(result) == 2
        for checksum in result.values():
            assert len(checksum) == 64

    def test_generate_checksums_writes_to_file(self, tmp_path: Path):
        from release.rc.release_tag import ReleaseTagGenerator

        test_dir = tmp_path / "artifacts"
        test_dir.mkdir()
        (test_dir / "test.txt").write_text("test content")

        output_file = str(tmp_path / "checksums_output.txt")
        gen = ReleaseTagGenerator(version="0.4.0-alpha1")
        result = gen.generate_checksums(str(test_dir), output_file=output_file)

        assert Path(output_file).exists()
        with open(output_file, "r") as f:
            content = f.read()
        assert len(result) > 0
        first_hash = list(result.values())[0]
        assert first_hash in content
