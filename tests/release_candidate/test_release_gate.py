"""
Tests for release gate validation and quality gate management.

Covers:
- Quality gate registration and evaluation
- Gate status transitions (PASS/FAIL/WARN/SKIP)
- Promotion recommendation logic
- Blocking issue resolution flow
- RC stage transition rules
"""

from __future__ import annotations

import pytest

from release.rc.rc_validator import (
    GateResult,
    GateStatus,
    RCValidationResult,
    RCValidator,
    ValidationGate,
)
from release.rc.release_candidate import (
    BlockingIssue,
    ChangelogEntry,
    GoNoGoDecision,
    GoNoGoRecord,
    IssueSeverity,
    RCStage,
    RCStatus,
    ReleaseCandidate,
)
from release.rc.version_manager import PreReleaseTag, VersionManager


class TestValidationGate:
    """Tests for ValidationGate and GateResult."""

    def test_gate_enum_values(self):
        assert ValidationGate.TESTS.value == "tests"
        assert ValidationGate.BENCHMARK.value == "benchmark"
        assert ValidationGate.SECURITY_SCAN.value == "security_scan"
        assert ValidationGate.API_COMPATIBILITY.value == "api_compatibility"
        assert ValidationGate.DOCUMENTATION.value == "documentation"
        assert ValidationGate.ROLLBACK_PLAN.value == "rollback_plan"

    def test_gate_status_enum(self):
        assert GateStatus.PASS.value == "PASS"
        assert GateStatus.FAIL.value == "FAIL"
        assert GateStatus.WARN.value == "WARN"
        assert GateStatus.SKIP.value == "SKIP"

    def test_gate_result_creation(self):
        result = GateResult(
            gate=ValidationGate.TESTS,
            status=GateStatus.PASS,
            message="All tests passed",
            details={"total": 100, "passed": 100},
        )
        assert result.gate == ValidationGate.TESTS
        assert result.status == GateStatus.PASS
        assert result.message == "All tests passed"
        assert result.details["total"] == 100
        assert result.executed_at != ""


class TestRCValidator:
    """Tests for RCValidator gate evaluation."""

    def test_validate_with_no_checks_registered(self):
        validator = RCValidator()
        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        assert result.all_passed is True
        assert result.promotion_recommended is True
        for gate_result in result.gate_results:
            assert gate_result.status == GateStatus.SKIP

    def test_validate_with_passing_checks(self):
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: True)
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: (True, "Benchmark OK"))

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        assert result.all_passed is True
        assert result.promotion_recommended is True

    def test_validate_with_failing_checks(self):
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: False)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        assert result.all_passed is False
        assert result.promotion_recommended is False

    def test_validate_with_blocking_issues(self):
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: True)
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: True)

        blocking = BlockingIssue(
            id="test-1",
            description="Critical bug in risk engine",
            severity=IssueSeverity.CRITICAL,
        )
        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
            blocking_issues=[blocking],
        )
        result = validator.validate(status, target_stage="beta")
        assert result.all_passed is True
        assert result.promotion_recommended is False

    def test_validate_gate_individually(self):
        validator = RCValidator()
        validator.register_check(
            ValidationGate.SECURITY_SCAN,
            lambda ctx: GateResult(
                gate=ValidationGate.SECURITY_SCAN,
                status=GateStatus.PASS,
                message="No vulnerabilities",
            ),
        )
        result = validator.validate_gate(ValidationGate.SECURITY_SCAN)
        assert result.status == GateStatus.PASS
        assert result.message == "No vulnerabilities"

    def test_is_gate_registered(self):
        validator = RCValidator()
        assert validator.is_gate_registered(ValidationGate.TESTS) is False
        validator.register_check(ValidationGate.TESTS, lambda ctx: True)
        assert validator.is_gate_registered(ValidationGate.TESTS) is True

    def test_validate_beta_to_rc(self):
        validator = RCValidator()
        for gate in [
            ValidationGate.TESTS,
            ValidationGate.BENCHMARK,
            ValidationGate.SECURITY_SCAN,
            ValidationGate.API_COMPATIBILITY,
        ]:
            validator.register_check(gate, lambda ctx: True)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.BETA,
        )
        result = validator.validate(status, target_stage="rc")
        assert len(result.gate_results) == 4
        assert result.all_passed is True
        assert result.promotion_recommended is True

    def test_validate_rc_to_ga(self):
        validator = RCValidator()
        for gate in [
            ValidationGate.TESTS,
            ValidationGate.BENCHMARK,
            ValidationGate.SECURITY_SCAN,
            ValidationGate.API_COMPATIBILITY,
            ValidationGate.DOCUMENTATION,
            ValidationGate.ROLLBACK_PLAN,
        ]:
            validator.register_check(gate, lambda ctx: True)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.RC,
        )
        result = validator.validate(status, target_stage="ga")
        assert len(result.gate_results) == 6
        assert result.all_passed is True
        assert result.promotion_recommended is True

    def test_get_failed_gates(self):
        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, lambda ctx: False)
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: True)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        failed = result.get_failed_gates()
        assert len(failed) == 1
        assert failed[0].gate == ValidationGate.TESTS

    def test_get_warning_gates(self):
        validator = RCValidator()
        validator.register_check(
            ValidationGate.TESTS,
            lambda ctx: GateResult(
                gate=ValidationGate.TESTS,
                status=GateStatus.WARN,
                message="Coverage below threshold",
            ),
        )
        validator.register_check(ValidationGate.BENCHMARK, lambda ctx: True)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        warnings = result.get_warning_gates()
        assert len(warnings) == 1
        assert warnings[0].gate == ValidationGate.TESTS

    def test_exception_in_check_function(self):
        validator = RCValidator()

        def bad_check(ctx):
            raise RuntimeError("Unexpected failure")

        validator.register_check(ValidationGate.TESTS, bad_check)

        status = RCStatus(
            version="0.4.0-alpha1",
            current_stage=RCStage.ALPHA,
        )
        result = validator.validate(status, target_stage="beta")
        assert result.all_passed is False
        failed = result.get_failed_gates()
        assert len(failed) == 1
        assert "Unexpected failure" in failed[0].message


class TestReleaseCandidate:
    """Tests for ReleaseCandidate lifecycle management."""

    def test_start_release_candidate(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        status = rc.start("alpha")
        assert status.current_stage == RCStage.ALPHA
        assert status.start_date != ""
        assert status.release_branch == "release/0.4.0-alpha1-alpha"

    def test_start_twice_raises(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        with pytest.raises(RuntimeError, match="already been started"):
            rc.start("beta")

    def test_promote_alpha_to_beta(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        status = rc.promote("beta")
        assert status.current_stage == RCStage.BETA

    def test_promote_with_blocking_issues(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.record_blocking_issue("Critical bug", severity="critical")
        with pytest.raises(RuntimeError, match="blocking issue"):
            rc.promote("beta")

    def test_promote_with_force(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.record_blocking_issue("Critical bug", severity="critical")
        status = rc.promote("beta", force=True)
        assert status.current_stage == RCStage.BETA

    def test_promote_invalid_transition(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        with pytest.raises(ValueError, match="Cannot promote"):
            rc.promote("rc")

    def test_full_lifecycle(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        rc.promote("rc")
        status = rc.promote("ga")
        assert status.current_stage == RCStage.GA
        assert status.promotion_recommendation == "released"

    def test_rollback(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.promote("beta")
        status = rc.rollback("alpha")
        assert status.current_stage == RCStage.ALPHA

    def test_deprecate(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        status = rc.deprecate()
        assert status.current_stage == RCStage.DEPRECATED

    def test_blocking_issue_lifecycle(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        issue = rc.record_blocking_issue("Bug", severity="major")
        assert issue.id in [i.id for i in rc.all_issues]
        assert len(rc.blocking_issues) == 1

        resolved = rc.resolve_issue(issue.id)
        assert resolved is not None
        assert resolved.resolved is True
        assert len(rc.blocking_issues) == 0

    def test_changelog_accumulation(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.add_changelog_entry("Added feature X", change_type="added", author="dev1")
        rc.add_changelog_entry("Fixed bug Y", change_type="fixed", author="dev2")

        changelog = rc.changelog
        assert len(changelog) == 2
        assert changelog[0].description == "Added feature X"
        assert changelog[1].change_type == "fixed"

    def test_go_no_go_decision(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        record = rc.record_go_no_go("GO", "All tests pass", "QA Lead")
        assert record.decision == GoNoGoDecision.GO
        assert rc.go_no_go == GoNoGoDecision.GO

    def test_readiness_score_by_stage(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        score = rc.get_readiness_score()
        assert 0.0 <= score <= 1.0

    def test_readiness_score_improves_with_go(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        rc.record_go_no_go("GO", "Ready", "QA")
        score = rc.get_readiness_score()
        base_score = 0.25
        expected_max = min(1.0, base_score + 0.15)
        assert score <= expected_max + 0.01

    def test_generate_release_tag(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        tag = rc.generate_release_tag()
        assert "0.4.0" in tag
        assert "alpha" in tag

    def test_custom_release_branch(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        status = rc.start("alpha", release_branch="feature/custom-branch")
        assert status.release_branch == "feature/custom-branch"

    def test_blocking_issue_severity_levels(self):
        rc = ReleaseCandidate(version="0.4.0-alpha1")
        rc.start("alpha")
        for sev in ["blocker", "critical", "major", "minor"]:
            issue = rc.record_blocking_issue(f"Issue at {sev}", severity=sev)
            assert issue.severity == IssueSeverity(sev)


class TestVersionManagerIntegration:
    """Tests for VersionManager used in release gates."""

    def test_version_parse_rc(self):
        vm = VersionManager()
        info = vm.parse("0.4.0-alpha1-rc1")
        assert info.major == 0
        assert info.minor == 4
        assert info.patch == 0
        assert info.pre_release == PreReleaseTag.ALPHA
        assert info.pre_release_num == 1
        assert info.sub_tag == "-rc1"

    def test_version_compare(self):
        vm = VersionManager()
        # alpha < rc in standard semver ordering
        info_alpha = vm.parse("0.4.0-alpha1")
        info_rc = vm.parse("0.4.0-alpha1-rc1")
        assert info_alpha < info_rc

    def test_version_generate_tag(self):
        vm = VersionManager()
        tag = vm.generate_tag(
            "0.4.0-alpha1",
            pre_release=PreReleaseTag.RC,
            pre_release_num=1,
            prefix="v",
        )
        assert tag == "v0.4.0-rc.1"

    def test_version_constraint_check(self):
        vm = VersionManager()
        assert vm.check_constraint("0.4.0", ">=0.4.0") is True
        assert vm.check_constraint("0.3.0", ">=0.4.0") is False
        assert vm.check_constraint("0.4.5", "<0.4.0") is False
        assert vm.check_constraint("0.4.0", "~0.4.0") is True
        assert vm.check_constraint("0.5.0", "~0.4.0") is False
        assert vm.check_constraint("1.0.0", "^0.4.0") is False
        assert vm.check_constraint("0.4.5", "^0.4.0") is True


class TestRCStatus:
    """Tests for RCStatus data class."""

    def test_default_creation(self):
        status = RCStatus()
        assert status.version == ""
        assert status.current_stage == RCStage.ALPHA
        assert status.readiness_score == 0.0

    def test_custom_creation(self):
        status = RCStatus(
            version="1.0.0",
            current_stage=RCStage.RC,
            readiness_score=0.75,
        )
        assert status.version == "1.0.0"
        assert status.current_stage == RCStage.RC
        assert status.readiness_score == 0.75
        assert status.promotion_recommendation == "blocked"
