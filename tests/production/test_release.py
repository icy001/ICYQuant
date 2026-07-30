"""
Release validation tests for the ICYQuant release process.

Tests version manager functionality, RC promotion workflow,
release candidate validation gates, deployment validation,
rollback capability, SBOM generation, release manifest generation,
and release notes generation.
"""

import os
import tempfile
import time

import pytest

from release.rc import (
    BlockingIssue,
    ChangelogEntry,
    GateResult,
    GateStatus,
    GoNoGoDecision,
    GoNoGoRecord,
    IssueSeverity,
    PreReleaseTag,
    RCStage,
    RCStatus,
    RCValidator,
    ReleaseCandidate,
    ValidationGate,
    VersionInfo,
    VersionManager,
)

from release.validation import (
    DeploymentCheck,
    DeploymentResult,
    DeploymentValidator,
    RollbackResult,
    RollbackStep,
    RollbackValidator,
)

from release.packaging import (
    BuildMetadata,
    CommitEntry,
    DependencyInfo,
    InfrastructureRequirement,
    PackageInfo,
    ReleaseManifest,
    ReleaseManifestResult,
    ReleaseNotesGenerator,
    ReleaseNotesResult,
    ReleaseSection,
    SBOMGenerator,
    SBOMResult,
)


class TestVersionManager:
    """Test version manager functionality."""

    def test_parse_simple_version(self):
        """Test parsing a simple semantic version."""
        vm = VersionManager()
        info = vm.parse("1.2.3")

        assert isinstance(info, VersionInfo)
        assert info.major == 1
        assert info.minor == 2
        assert info.patch == 3
        assert info.pre_release is None
        assert info.pre_release_num is None

    def test_parse_prerelease_version(self):
        """Test parsing a version with pre-release tag."""
        vm = VersionManager()
        info = vm.parse("1.2.3-alpha.1")

        assert info.pre_release == PreReleaseTag.ALPHA
        assert info.pre_release_num == 1

    def test_parse_version_with_build(self):
        """Test parsing a version with build metadata."""
        vm = VersionManager()
        info = vm.parse("1.2.3+build.42")

        assert info.build_metadata == "build.42"

    def test_parse_invalid_version(self):
        """Test that invalid versions raise ValueError."""
        vm = VersionManager()
        with pytest.raises(ValueError):
            vm.parse("not.a.version")

    def test_compare_versions(self):
        """Test version comparison logic."""
        vm = VersionManager()

        assert vm.compare("1.0.0", "2.0.0") == -1
        assert vm.compare("2.0.0", "1.0.0") == 1
        assert vm.compare("1.0.0", "1.0.0") == 0

    def test_compare_prerelease_ordering(self):
        """Test pre-release version ordering (alpha < beta < rc)."""
        vm = VersionManager()

        assert vm.compare("1.0.0-alpha", "1.0.0-beta") == -1
        assert vm.compare("1.0.0-beta", "1.0.0-rc") == -1
        assert vm.compare("1.0.0-rc", "1.0.0") == -1

    def test_bump_patch(self):
        """Test bumping patch version."""
        vm = VersionManager()
        info = vm.bump("1.2.3", part="patch")

        assert info.major == 1
        assert info.minor == 2
        assert info.patch == 4

    def test_bump_minor(self):
        """Test bumping minor version."""
        vm = VersionManager()
        info = vm.bump("1.2.3", part="minor")

        assert info.major == 1
        assert info.minor == 3
        assert info.patch == 0

    def test_bump_major(self):
        """Test bumping major version."""
        vm = VersionManager()
        info = vm.bump("1.2.3", part="major")

        assert info.major == 2
        assert info.minor == 0
        assert info.patch == 0

    def test_bump_invalid_part(self):
        """Test that invalid bump part raises ValueError."""
        vm = VersionManager()
        with pytest.raises(ValueError):
            vm.bump("1.2.3", part="invalid")

    def test_generate_release_tag(self):
        """Test release tag generation."""
        vm = VersionManager()
        tag = vm.generate_release_tag("1.2.3", pre_release=PreReleaseTag.RC, pre_release_num=2)

        assert tag == "v1.2.3-rc.2"

    def test_generate_tag_without_prerelease(self):
        """Test tag generation without pre-release."""
        vm = VersionManager()
        tag = vm.generate_tag("1.2.3")

        assert tag == "1.2.3"

    def test_version_constraint_checks(self):
        """Test version constraint checking."""
        vm = VersionManager()

        assert vm.check_constraint("2.0.0", ">=1.0.0") is True
        assert vm.check_constraint("0.9.0", ">=1.0.0") is False
        assert vm.check_constraint("1.5.0", ">1.0.0") is True
        assert vm.check_constraint("1.0.0", "<2.0.0") is True
        assert vm.check_constraint("2.0.0", "<=2.0.0") is True

    def test_bump_prerelease(self):
        """Test bumping pre-release number."""
        vm = VersionManager()
        info = vm.bump_prerelease("1.2.3-alpha.1", PreReleaseTag.ALPHA, pre_release_num=2)

        assert info.pre_release == PreReleaseTag.ALPHA
        assert info.pre_release_num == 2

    def test_list_prereleases(self):
        """Test generating a list of pre-release versions."""
        vm = VersionManager()
        tags = vm.list_prereleases("1.0.0", PreReleaseTag.BETA, start=1, end=3)

        assert len(tags) == 3
        assert tags[0] == "1.0.0-beta.1"
        assert tags[1] == "1.0.0-beta.2"
        assert tags[2] == "1.0.0-beta.3"


class TestRCPromotionWorkflow:
    """Test RC promotion workflow."""

    def test_start_rc(self):
        """Test starting a release candidate at alpha stage."""
        rc = ReleaseCandidate(version="1.2.0")
        status = rc.start("alpha")

        assert isinstance(status, RCStatus)
        assert status.version == "1.2.0"
        assert status.current_stage == RCStage.ALPHA
        assert status.start_date != ""
        assert "release/1.2.0-alpha" in status.release_branch

    def test_start_rc_custom_branch(self):
        """Test starting RC with a custom release branch."""
        rc = ReleaseCandidate(version="1.2.0")
        status = rc.start("beta", release_branch="feature-custom-branch")

        assert status.current_stage == RCStage.BETA
        assert status.release_branch == "feature-custom-branch"

    def test_promote_alpha_to_beta(self):
        """Test promoting RC from alpha to beta."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        status = rc.promote("beta")

        assert status.current_stage == RCStage.BETA
        assert status.promotion_recommendation in ("progressing", "ready_for_promotion", " progressing")

    def test_promote_beta_to_rc(self):
        """Test promoting RC from beta to rc."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.promote("beta")
        status = rc.promote("rc")

        assert status.current_stage == RCStage.RC

    def test_promote_rc_to_ga(self):
        """Test promoting RC from rc to ga."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        status = rc.promote("ga")

        assert status.current_stage == RCStage.GA
        assert status.promotion_recommendation == "released"

    def test_promote_blocked_by_issues(self):
        """Test that promotion is blocked by unresolved issues."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.record_blocking_issue("Critical bug", severity="critical")

        with pytest.raises(RuntimeError, match="blocking"):
            rc.promote("beta")

    def test_promote_forced(self):
        """Test forced promotion bypassing blocking issues."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.record_blocking_issue("Critical bug", severity="critical")
        status = rc.promote("beta", force=True)

        assert status.current_stage == RCStage.BETA

    def test_invalid_promotion_path(self):
        """Test that invalid stage transitions raise ValueError."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")

        with pytest.raises(ValueError):
            rc.promote("ga")

    def test_rollback(self):
        """Test rolling back a stage."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.promote("beta")
        status = rc.rollback("alpha")

        assert status.current_stage == RCStage.ALPHA

    def test_deprecate(self):
        """Test deprecating a release candidate."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        status = rc.deprecate()

        assert status.current_stage == RCStage.DEPRECATED

    def test_changelog_accumulation(self):
        """Test changelog entry accumulation."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        entry = rc.add_changelog_entry("Added new feature", change_type="added", author="dev1")

        assert isinstance(entry, ChangelogEntry)
        assert entry.description == "Added new feature"
        assert entry.change_type == "added"
        assert entry.author == "dev1"

        status = rc.get_status()
        assert status.changelog_accumulated == 1

    def test_blocking_issue_resolution(self):
        """Test resolving blocking issues."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        issue = rc.record_blocking_issue("Bug to fix", severity="major")

        assert len(rc.blocking_issues) == 1

        resolved = rc.resolve_issue(issue.id)
        assert resolved is not None
        assert resolved.resolved is True

        assert len(rc.blocking_issues) == 0

    def test_go_no_go_decision(self):
        """Test recording Go/No-Go decisions."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        record = rc.record_go_no_go("GO", "All tests pass", "release_manager")

        assert isinstance(record, GoNoGoRecord)
        assert record.decision == GoNoGoDecision.GO
        assert rc.go_no_go == GoNoGoDecision.GO

    def test_readiness_score(self):
        """Test readiness score calculation."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        score = rc.get_readiness_score()

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_generate_release_tag(self):
        """Test generating a release tag."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        tag = rc.generate_release_tag()

        assert "v1.2.0" in tag
        assert "alpha" in tag

    def test_already_started_raises(self):
        """Test that starting an already-started RC raises RuntimeError."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")

        with pytest.raises(RuntimeError):
            rc.start("alpha")


class TestRCValidationGates:
    """Test release candidate validation gates."""

    def test_all_gates_pass(self):
        """Test validation when all gates pass."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.promote("beta")
        status = rc.get_status()

        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: True)
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: True)
        validator.register_check(ValidationGate.SECURITY_SCAN, lambda ctx: True)
        validator.register_check(ValidationGate.API_COMPATIBILITY, lambda ctx: True)

        result = validator.validate(status, target_stage="rc")

        assert result.all_passed is True
        assert result.promotion_recommended is True
        assert result.target_stage == RCStage.RC

    def test_gate_fails_with_issue(self):
        """Test validation with a failing gate and blocking issue."""
        rc = ReleaseCandidate(version="1.2.0")
        rc.start("alpha")
        rc.promote("beta")
        rc.record_blocking_issue("Critical issue", severity="blocker")
        status = rc.get_status()

        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: (False, "Tests failed"))
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: True)

        result = validator.validate(status, target_stage="rc")

        assert result.all_passed is False
        assert result.promotion_recommended is False

    def test_gate_registration_check(self):
        """Test gate registration verification."""
        validator = RCValidator()
        assert validator.is_gate_registered(ValidationGate.TESTS) is False

        validator.register_check(ValidationGate.TESTS, lambda ctx: True)
        assert validator.is_gate_registered(ValidationGate.TESTS) is True

    def test_single_gate_validation(self):
        """Test validating a single gate."""
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: True)

        result = validator.validate_gate(ValidationGate.TESTS)
        assert result.status == GateStatus.PASS

    def test_single_gate_fail(self):
        """Test single gate validation failure."""
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: (False, "Test failed"))

        result = validator.validate_gate(ValidationGate.TESTS)
        assert result.status == GateStatus.FAIL
        assert "Test failed" in result.message

    def test_unregistered_gate_skipped(self):
        """Test that unregistered gates are skipped."""
        validator = RCValidator()
        result = validator.validate_gate(ValidationGate.TESTS)

        assert result.status == GateStatus.SKIP

    def test_gate_result_properties(self):
        """Test GateResult dataclass properties."""
        result = GateResult(
            gate=ValidationGate.TESTS,
            status=GateStatus.PASS,
            message="All tests passed",
        )
        assert result.gate == ValidationGate.TESTS
        assert result.status == GateStatus.PASS
        assert result.message == "All tests passed"

    def test_rc_validation_result_methods(self):
        """Test RCValidationResult query methods."""
        from release.rc.rc_validator import RCValidationResult

        rc_result = RCValidationResult(
            version="1.0.0",
            target_stage=RCStage.RC,
            source_stage=RCStage.BETA,
            gate_results=[
                GateResult(gate=ValidationGate.TESTS, status=GateStatus.PASS),
                GateResult(gate=ValidationGate.BENCHMARK, status=GateStatus.FAIL),
                GateResult(gate=ValidationGate.SECURITY_SCAN, status=GateStatus.WARN),
            ],
            all_passed=False,
            has_warnings=True,
            promotion_recommended=False,
            summary="1/3 gates passed",
        )

        assert rc_result.get_gate_status(ValidationGate.TESTS) == GateStatus.PASS
        assert rc_result.get_gate_status(ValidationGate.BENCHMARK) == GateStatus.FAIL
        assert rc_result.get_gate_status(ValidationGate.SECURITY_SCAN) == GateStatus.WARN
        assert rc_result.get_gate_status(ValidationGate.DOCUMENTATION) is None

        failed = rc_result.get_failed_gates()
        assert len(failed) == 1
        assert failed[0].gate == ValidationGate.BENCHMARK

        warnings = rc_result.get_warning_gates()
        assert len(warnings) == 1
        assert warnings[0].gate == ValidationGate.SECURITY_SCAN


class TestDeploymentValidation:
    """Test deployment validation."""

    def test_deployment_validator_run(self):
        """Test running the deployment validator."""
        validator = DeploymentValidator()
        result = validator.run()

        assert isinstance(result, DeploymentResult)
        assert len(result.checks) >= 5
        assert isinstance(result.checks[0], DeploymentCheck)
        assert result.total_duration_ms >= 0

    def test_deployment_result_properties(self):
        """Test DeploymentResult dataclass properties."""
        result = DeploymentResult(
            overall_passed=True,
            total_duration_ms=500.0,
            checks=[
                DeploymentCheck(check_name="A", passed=True, duration_ms=100.0),
                DeploymentCheck(check_name="B", passed=False, duration_ms=200.0),
            ],
        )
        assert result.pass_rate == pytest.approx(0.5)
        assert len(result.failed_checks) == 1

    def test_deployment_result_empty_checks(self):
        """Test pass_rate with empty checks."""
        result = DeploymentResult(
            overall_passed=False,
            total_duration_ms=0.0,
            checks=[],
        )
        assert result.pass_rate == 0.0


class TestRollbackCapability:
    """Test rollback capability."""

    def test_rollback_validator_run(self):
        """Test running the rollback validator."""
        validator = RollbackValidator()
        result = validator.run()

        assert isinstance(result, RollbackResult)
        assert len(result.steps) >= 3
        assert isinstance(result.steps[0], RollbackStep)
        assert result.total_duration_ms >= 0

    def test_rollback_result_properties(self):
        """Test RollbackResult dataclass properties."""
        result = RollbackResult(
            overall_passed=True,
            total_duration_ms=1000.0,
            steps=[
                RollbackStep(step_name="A", passed=True, duration_ms=100.0, rto_ms=5000.0),
                RollbackStep(step_name="B", passed=True, duration_ms=200.0, rto_ms=3000.0),
            ],
            rto_achieved_ms=5000.0,
            rto_target_ms=300000.0,
            rpo_achieved_seconds=60.0,
            rpo_target_seconds=300.0,
            zero_downtime=True,
        )
        assert result.rto_met is True
        assert result.rpo_met is True
        assert result.zero_downtime is True
        assert result.pass_rate == 1.0

    def test_rollback_rto_exceeded(self):
        """Test rollback RTO exceeded scenario."""
        result = RollbackResult(
            overall_passed=False,
            total_duration_ms=5000.0,
            rto_achieved_ms=500000.0,
            rto_target_ms=300000.0,
        )
        assert result.rto_met is False


class TestSBOMGeneration:
    """Test SBOM generation."""

    def test_sbom_generator_creation(self):
        """Test SBOMGenerator initialization."""
        gen = SBOMGenerator(project_name="ICYQuant", project_version="1.2.0")
        assert gen.project_name == "ICYQuant"
        assert gen.project_version == "1.2.0"

    def test_add_package(self):
        """Test adding a package to the SBOM."""
        gen = SBOMGenerator()
        gen.add_package("numpy", "1.24.0", ecosystem="pypi", license="BSD-3-Clause")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = gen.generate(output_dir=tmpdir)
            assert isinstance(result, SBOMResult)
            assert result.total_packages >= 1
            assert result.success is True

    def test_add_docker_base_image(self):
        """Test adding Docker base image to SBOM."""
        gen = SBOMGenerator()
        gen.set_docker_base_image("python:3.11-slim")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = gen.generate(output_dir=tmpdir)
            assert result.total_packages >= 1

    def test_license_compliance(self):
        """Test license compliance checking."""
        gen = SBOMGenerator()
        gen.add_package("numpy", "1.24.0", license="BSD-3-Clause")
        gen.add_package("proprietary-lib", "1.0.0", license="Proprietary")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = gen.generate(output_dir=tmpdir)
            assert isinstance(result, SBOMResult)
            assert result.license_compliant is False
            assert len(result.license_issues) > 0

    def test_vulnerability_tracking(self):
        """Test vulnerability tracking in SBOM."""
        gen = SBOMGenerator()
        gen.add_package("vuln-pkg", "1.0.0", vulnerabilities=["CRITICAL-CVE-001", "HIGH-CVE-002"])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = gen.generate(output_dir=tmpdir)
            assert result.has_vulnerabilities is True
            assert result.critical_vulnerabilities == 1
            assert result.high_vulnerabilities == 1
            assert result.vulnerability_count == 2
            assert result.risk_level == "critical"

    def test_sbom_result_risk_levels(self):
        """Test SBOMResult risk level property."""
        result = SBOMResult(
            success=True,
            vulnerability_count=3,
            critical_vulnerabilities=0,
            high_vulnerabilities=0,
        )
        assert result.risk_level == "medium"

        result2 = SBOMResult(
            success=True,
            vulnerability_count=0,
        )
        assert result2.risk_level == "low"

    def test_sbom_output_files(self):
        """Test SBOM output file generation."""
        gen = SBOMGenerator()
        gen.add_package("flask", "3.0.0")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = gen.generate(output_dir=tmpdir)
            assert len(result.output_files) == 2
            for f in result.output_files:
                assert os.path.isfile(f)


class TestReleaseManifest:
    """Test release manifest generation."""

    def test_manifest_creation(self):
        """Test creating a release manifest."""
        manifest = ReleaseManifest("1.2.0", git_commit="abc1234", git_branch="main")
        assert manifest.version == "1.2.0"
        assert manifest.git_commit == "abc1234"

    def test_manifest_add_dependency(self):
        """Test adding dependencies to the manifest."""
        manifest = ReleaseManifest("1.2.0")
        manifest.add_dependency("numpy", "1.24.0", license="BSD-3-Clause")
        manifest.add_dependency("flask", "3.0.0", license="BSD-3-Clause", is_direct=True)

        result = manifest.generate()
        assert isinstance(result, ReleaseManifestResult)

    def test_manifest_add_infrastructure(self):
        """Test adding infrastructure requirements."""
        manifest = ReleaseManifest("1.2.0")
        manifest.add_infrastructure_requirement(
            component="PostgreSQL",
            min_version="14.0",
            recommended_version="15.0",
            purpose="Database",
        )

        result = manifest.generate()
        assert isinstance(result, ReleaseManifestResult)

    def test_manifest_set_build_metadata(self):
        """Test setting build metadata."""
        manifest = ReleaseManifest("1.2.0")
        manifest.set_build_metadata(build_id="build-001", build_number=1, build_environment="CI")

        result = manifest.generate()
        assert isinstance(result, ReleaseManifestResult)

    def test_manifest_generate(self):
        """Test full manifest generation."""
        manifest = ReleaseManifest("1.2.0", git_commit="abc12345")
        manifest.add_dependency("numpy", "1.24.0")
        manifest.add_infrastructure_requirement(
            component="Redis",
            min_version="6.0",
            recommended_version="7.0",
            purpose="Caching",
        )
        manifest.set_build_metadata(build_id="build-001", build_number=1)

        result = manifest.generate()
        assert isinstance(result, ReleaseManifestResult)
        assert result.success is True
        assert result.manifest_version == "1.0.0"
        assert result.completeness_score > 0.0

    def test_manifest_to_dict(self):
        """Test manifest serialization to dict."""
        manifest = ReleaseManifest("1.2.0")
        data = manifest.to_dict()

        assert isinstance(data, dict)
        assert "version" in data
        assert data["version"] == "1.2.0"

    def test_manifest_to_json(self):
        """Test manifest serialization to JSON."""
        manifest = ReleaseManifest("1.2.0")
        json_str = manifest.to_json()

        assert isinstance(json_str, str)
        assert "1.2.0" in json_str

    def test_manifest_result_validity(self):
        """Test ReleaseManifestResult validity property."""
        result = ReleaseManifestResult(
            success=True,
            manifest_version="1.0.0",
            manifest_hash="abc123",
            completeness_score=0.9,
            is_complete=True,
        )
        assert result.is_valid is True

    def test_manifest_result_invalid(self):
        """Test invalid manifest result."""
        result = ReleaseManifestResult(
            success=False,
            manifest_version="1.0.0",
            manifest_hash="",
            completeness_score=0.3,
            is_complete=False,
            validation_errors=["Missing required field: version"],
        )
        assert result.is_valid is False

    def test_dependency_info_creation(self):
        """Test DependencyInfo dataclass creation."""
        dep = DependencyInfo(name="numpy", version="1.24.0", license="BSD-3-Clause")
        assert dep.name == "numpy"
        assert dep.version == "1.24.0"

    def test_build_metadata_creation(self):
        """Test BuildMetadata dataclass creation."""
        bm = BuildMetadata(
            build_id="build-001",
            build_number=1,
            build_timestamp="2024-01-01T00:00:00Z",
            build_environment="CI",
            builder_name="Builder",
            builder_version="1.0",
            python_version="3.11.0",
            platform_system="Linux",
            platform_release="5.15",
        )
        assert bm.build_id == "build-001"
        assert bm.build_number == 1


class TestReleaseNotes:
    """Test release notes generation."""

    def test_release_notes_generator(self):
        """Test release notes generator initialization."""
        gen = ReleaseNotesGenerator("1.2.0")
        assert gen.version == "1.2.0"
        assert "1.2.0" in gen.title

    def test_add_commit(self):
        """Test adding a commit to release notes."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_commit("abc1234", "feat: add new feature", author="dev1")

        result = gen.generate()
        assert isinstance(result, ReleaseNotesResult)
        assert result.success is True
        assert result.total_entries > 0
        assert "feat" in result.markdown_content

    def test_add_multiple_commits(self):
        """Test adding multiple commits of different types."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_commit("abc1", "feat: new feature", author="dev1")
        gen.add_commit("abc2", "fix: bug fix", author="dev2")
        gen.add_commit("abc3", "feat: another feature", author="dev3")
        gen.add_commit("abc4", "docs: update docs", author="dev1")

        result = gen.generate()
        assert result.features_count == 2
        assert result.fixes_count == 1
        assert len(result.authors) >= 2

    def test_add_breaking_change(self):
        """Test adding a breaking change."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_commit("abc1", "feat!: breaking change", author="dev1")

        result = gen.generate()
        assert result.breaking_changes_count >= 1

    def test_add_known_issue(self):
        """Test adding known issues to release notes."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_known_issue("Memory leak in edge case")

        result = gen.generate()
        assert "Memory leak" in result.markdown_content

    def test_add_migration_note(self):
        """Test adding migration notes."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_migration_note("Run database migration before deploying")

        result = gen.generate()
        assert "Migration" in result.markdown_content

    def test_release_section_order(self):
        """Test that sections are in the correct order."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_commit("abc1", "feat: new feature", author="dev1")
        gen.add_commit("abc2", "fix: bug fix", author="dev2")

        result = gen.generate()
        section_titles = [s.title for s in result.sections]
        features_idx = section_titles.index("New Features")
        fixes_idx = section_titles.index("Bug Fixes")
        assert features_idx < fixes_idx

    def test_release_notes_result_properties(self):
        """Test ReleaseNotesResult dataclass properties."""
        result = ReleaseNotesResult(
            success=True,
            title="Test Release",
            version="1.2.0",
            generated_at="2024-01-01T00:00:00Z",
            markdown_content="# Test",
            total_entries=5,
            features_count=3,
            fixes_count=2,
        )
        assert result.success is True
        assert result.title == "Test Release"
        assert result.features_count == 3
        assert result.fixes_count == 2

    def test_commit_entry_parsing(self):
        """Test CommitEntry creation with conventional commits."""
        gen = ReleaseNotesGenerator("1.2.0")
        gen.add_commit("abc1", "feat(risk): add new check", author="dev1")

        result = gen.generate()
        assert result.features_count == 1

    def test_release_section_properties(self):
        """Test ReleaseSection dataclass properties."""
        section = ReleaseSection(
            title="New Features",
            entries=["- Added feature A", "- Added feature B"],
        )
        assert section.title == "New Features"
        assert len(section.entries) == 2