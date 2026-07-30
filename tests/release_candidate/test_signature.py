"""
Tests for release signature validation, certificate chain verification,
and release integrity attestation.

Covers:
- Release signature file existence and structure
- Signature algorithm and format
- Certificate chain completeness
- Signatory information
- Verification status
- Build provenance
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_RC_DIR = PROJECT_ROOT / "release" / "rc"
RELEASE_ARTIFACTS_DIR = PROJECT_ROOT / "release" / "artifacts"


@pytest.fixture
def release_signature():
    sig_path = RELEASE_RC_DIR / "release_signature.json"
    if not sig_path.exists():
        pytest.skip("release_signature.json not found")
    with open(sig_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def provenance():
    prov_path = RELEASE_ARTIFACTS_DIR / "provenance.json"
    if not prov_path.exists():
        pytest.skip("provenance.json not found")
    with open(prov_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def release_metadata():
    meta_path = RELEASE_ARTIFACTS_DIR / "release_metadata.json"
    if not meta_path.exists():
        pytest.skip("release_metadata.json not found")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sbom():
    sbom_path = RELEASE_ARTIFACTS_DIR / "sbom.json"
    if not sbom_path.exists():
        pytest.skip("sbom.json not found")
    with open(sbom_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestReleaseSignature:
    """Tests for release signature structure and validation."""

    def test_signature_file_exists(self):
        sig = RELEASE_RC_DIR / "release_signature.json"
        assert sig.exists(), "release_signature.json must exist"

    def test_signature_has_version(self, release_signature: Dict[str, Any]):
        assert release_signature.get("version") == "v0.4.0-alpha1-rc1"

    def test_signature_has_build_id(self, release_signature: Dict[str, Any]):
        build_id = release_signature.get("build_id", "")
        assert build_id.startswith("build-")
        assert "alpha1-rc1" in build_id

    def test_signature_has_build_timestamp(self, release_signature: Dict[str, Any]):
        assert release_signature.get("build_timestamp", "") != ""

    def test_signature_has_checksums(self, release_signature: Dict[str, Any]):
        checksums = release_signature.get("checksums", {})
        assert len(checksums) >= 4, "Must have checksums for at least 4 artifacts"

    def test_signature_has_signatures_section(self, release_signature: Dict[str, Any]):
        signatures = release_signature.get("signatures", {})
        assert "method" in signatures
        assert "algorithm" in signatures
        assert "signature_value" in signatures

    def test_signature_method_is_rsa(self, release_signature: Dict[str, Any]):
        signatures = release_signature["signatures"]
        assert "RSA" in signatures.get("method", "")

    def test_signature_algorithm_is_sha256(self, release_signature: Dict[str, Any]):
        signatures = release_signature["signatures"]
        assert "SHA256" in signatures.get("algorithm", "")

    def test_signature_value_is_base64(self, release_signature: Dict[str, Any]):
        import base64
        sig_value = release_signature["signatures"]["signature_value"]
        # Clean the value - mock data may contain whitespace/newlines
        cleaned = sig_value.strip().replace("\r", "").replace("\n", "")
        try:
            base64.b64decode(cleaned, validate=True)
        except Exception:
            pytest.fail("signature_value must be valid base64")

    def test_signature_has_certificate_chain(self, release_signature: Dict[str, Any]):
        signatures = release_signature["signatures"]
        chain = signatures.get("certificate_chain", [])
        assert len(chain) >= 2, "Certificate chain must have at least 2 certificates"

    def test_certificate_chain_has_ca(self, release_signature: Dict[str, Any]):
        chain = release_signature["signatures"]["certificate_chain"]
        ca_cert = chain[0]
        assert "CA" in ca_cert or "Certificate Authority" in ca_cert or "Signing" in ca_cert

    def test_verification_status_is_valid(self, release_signature: Dict[str, Any]):
        assert release_signature.get("verification_status") == "valid"

    def test_verification_timestamp_present(self, release_signature: Dict[str, Any]):
        assert release_signature.get("verification_timestamp", "") != ""


class TestSignatories:
    """Tests for signatory information completeness."""

    def test_has_signatories(self, release_signature: Dict[str, Any]):
        signatories = release_signature.get("signatories", [])
        assert len(signatories) >= 2, "Must have at least 2 signatories"

    def test_signatory_has_name(self, release_signature: Dict[str, Any]):
        for signatory in release_signature["signatories"]:
            assert signatory.get("name", "") != ""

    def test_signatory_has_role(self, release_signature: Dict[str, Any]):
        for signatory in release_signature["signatories"]:
            assert signatory.get("role", "") != ""

    def test_signatory_has_email(self, release_signature: Dict[str, Any]):
        for signatory in release_signature["signatories"]:
            email = signatory.get("email", "")
            assert "@" in email and "." in email, f"Invalid email: {email}"

    def test_signatory_has_key_fingerprint(self, release_signature: Dict[str, Any]):
        for signatory in release_signature["signatories"]:
            fp = signatory.get("public_key_fingerprint", "")
            assert fp.startswith("SHA256:"), "Key fingerprint must start with SHA256:"
            hash_part = fp.replace("SHA256:", "")
            assert len(hash_part) >= 60, (
                f"Fingerprint hash must be at least 60 hex chars, got {len(hash_part)}"
            )

    def test_signatory_has_timestamp(self, release_signature: Dict[str, Any]):
        for signatory in release_signature["signatories"]:
            assert signatory.get("signature_timestamp", "") != ""


class TestCertificateInfo:
    """Tests for certificate information completeness."""

    def test_has_certificate_info(self, release_signature: Dict[str, Any]):
        cert = release_signature.get("certificate_info", {})
        assert len(cert) > 0, "Must have certificate info"

    def test_cert_has_issuer(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        assert cert.get("issuer", "") != ""

    def test_cert_has_subject(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        assert cert.get("subject", "") != ""

    def test_cert_has_serial(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        serial = cert.get("serial_number", "")
        assert serial != ""
        assert ":" in serial or len(serial) >= 10

    def test_cert_valid_from_before_to(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        valid_from = cert.get("valid_from", "")
        valid_to = cert.get("valid_to", "")
        assert valid_from < valid_to, "Certificate validity must be positive"

    def test_cert_has_key_size(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        key_size = cert.get("key_size", 0)
        assert key_size >= 2048, f"Key size {key_size} must be at least 2048 bits"

    def test_cert_has_key_usage(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        usage = cert.get("key_usage", [])
        assert "digitalSignature" in usage

    def test_cert_has_extended_key_usage(self, release_signature: Dict[str, Any]):
        cert = release_signature["certificate_info"]
        ext_usage = cert.get("extended_key_usage", [])
        assert "codeSigning" in ext_usage


class TestProvenance:
    """Tests for SLSA build provenance."""

    def test_provenance_file_exists(self):
        prov = RELEASE_ARTIFACTS_DIR / "provenance.json"
        assert prov.exists(), "provenance.json must exist"

    def test_provenance_has_intoto_type(self, provenance: Dict[str, Any]):
        assert provenance.get("_type") == "https://in-toto.io/Statement/v1.0"

    def test_provenance_has_subjects(self, provenance: Dict[str, Any]):
        subjects = provenance.get("subject", [])
        assert len(subjects) >= 3, "Must have at least 3 subject artifacts"

    def test_provenance_subjects_have_digests(self, provenance: Dict[str, Any]):
        for subject in provenance["subject"]:
            assert "name" in subject
            assert "digest" in subject
            assert "sha256" in subject["digest"]

    def test_provenance_has_slsa_predicate(self, provenance: Dict[str, Any]):
        assert provenance.get("predicateType") == "https://slsa.dev/provenance/v1.0"

    def test_provenance_has_build_definition(self, provenance: Dict[str, Any]):
        predicate = provenance.get("predicate", {})
        build_def = predicate.get("buildDefinition", {})
        assert "buildType" in build_def
        assert "externalParameters" in build_def

    def test_provenance_has_external_parameters(self, provenance: Dict[str, Any]):
        build_def = provenance["predicate"]["buildDefinition"]
        ext_params = build_def.get("externalParameters", {})
        assert "source" in ext_params
        assert "builder" in ext_params

    def test_provenance_has_source_uri(self, provenance: Dict[str, Any]):
        ext_params = provenance["predicate"]["buildDefinition"]["externalParameters"]
        source = ext_params["source"]
        assert "uri" in source
        assert "icyquant" in source["uri"].lower() or "github" in source["uri"].lower()

    def test_provenance_has_resolved_dependencies(self, provenance: Dict[str, Any]):
        build_def = provenance["predicate"]["buildDefinition"]
        ext_params = build_def.get("externalParameters", {})
        deps = ext_params.get("resolvedDependencies", [])
        assert len(deps) >= 1, "Must have at least 1 resolved dependency"

    def test_provenance_has_run_details(self, provenance: Dict[str, Any]):
        predicate = provenance.get("predicate", {})
        run_details = predicate.get("runDetails", {})
        assert "builder" in run_details
        assert "metadata" in run_details

    def test_provenance_has_build_steps(self, provenance: Dict[str, Any]):
        build_steps = provenance["predicate"].get("buildSteps", [])
        assert len(build_steps) >= 5, "Must have at least 5 build steps"

    def test_provenance_build_steps_have_names(self, provenance: Dict[str, Any]):
        for step in provenance["predicate"]["buildSteps"]:
            assert "name" in step
            assert "description" in step


class TestSBOM:
    """Tests for Software Bill of Materials."""

    def test_sbom_file_exists(self):
        sbom = RELEASE_ARTIFACTS_DIR / "sbom.json"
        assert sbom.exists(), "sbom.json must exist"

    def test_sbom_has_metadata(self, sbom: Dict[str, Any]):
        assert "metadata" in sbom

    def test_sbom_has_components(self, sbom: Dict[str, Any]):
        components = sbom.get("components", [])
        assert len(components) > 0, "SBOM must list components"

    def test_sbom_has_spec_version(self, sbom: Dict[str, Any]):
        assert "specVersion" in sbom or "bomFormat" in sbom

    def test_sbom_component_has_name(self, sbom: Dict[str, Any]):
        for component in sbom.get("components", []):
            assert "name" in component

    def test_sbom_component_has_version(self, sbom: Dict[str, Any]):
        for component in sbom.get("components", []):
            assert "version" in component


class TestMetadataSigning:
    """Tests for release metadata signing consistency."""

    def test_metadata_signed(self, release_metadata: Dict[str, Any]):
        signing = release_metadata.get("signing", {})
        assert signing.get("signed") is True

    def test_metadata_signing_algorithm(self, release_metadata: Dict[str, Any]):
        signing = release_metadata.get("signing", {})
        assert "RSA" in signing.get("signature_algorithm", "")
        assert "SHA256" in signing.get("signature_algorithm", "")

    def test_metadata_signing_cert_issuer(self, release_metadata: Dict[str, Any]):
        signing = release_metadata.get("signing", {})
        assert signing.get("certificate_issuer") == "ICYQuant Release Signing CA"

    def test_metadata_signing_status_valid(self, release_metadata: Dict[str, Any]):
        signing = release_metadata.get("signing", {})
        assert signing.get("verification_status") == "valid"

    def test_metadata_slsa_level(self, release_metadata: Dict[str, Any]):
        provenance = release_metadata.get("provenance", {})
        assert provenance.get("slsa_level") == "2"

    def test_metadata_has_provenance_file_ref(self, release_metadata: Dict[str, Any]):
        provenance = release_metadata.get("provenance", {})
        assert provenance.get("provenance_file") == "release/artifacts/provenance.json"

    def test_metadata_has_sbom_file_ref(self, release_metadata: Dict[str, Any]):
        compliance = release_metadata.get("compliance", {})
        assert compliance.get("sbom_file") == "release/artifacts/sbom.json"
