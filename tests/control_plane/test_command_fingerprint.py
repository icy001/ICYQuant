"""Command fingerprint tests (Commit 29 Part 1.4 §6-8, §50).

A fingerprint binds principal, resource, action, target and parameters.
Canonical serialization keeps it stable across dict ordering; any mutation
breaks it (§50).
"""

from __future__ import annotations

from services.control_plane import fingerprint_command


class TestCommandFingerprint:
    def test_fingerprint_is_stable_sha256(self, make_command):
        command = make_command()
        digest = fingerprint_command(command)
        assert len(digest) == 64
        assert int(digest, 16) >= 0  # valid hex
        assert fingerprint_command(command) == digest

    def test_same_business_command_has_same_fingerprint(self, make_command):
        """Canonical JSON: dict ordering must not change the fingerprint (§8)."""
        a = make_command(parameters={"severity": "normal", "reason": "halt"})
        b = make_command(parameters={"reason": "halt", "severity": "normal"})
        assert fingerprint_command(a) == fingerprint_command(b)

    def test_principal_change_breaks_fingerprint(self, make_command):
        a = make_command(requested_by="ops-001")
        b = make_command(requested_by="ops-002")
        assert fingerprint_command(a) != fingerprint_command(b)

    def test_action_change_breaks_fingerprint(self, make_command):
        a = make_command(action="pause")
        b = make_command(action="kill")
        assert fingerprint_command(a) != fingerprint_command(b)

    def test_target_change_breaks_fingerprint(self, make_command):
        from services.control_plane import ControlTarget

        a = make_command(
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="production"
            )
        )
        b = make_command(
            target=ControlTarget(
                service="oms", instance="oms-secondary", environment="production"
            )
        )
        assert fingerprint_command(a) != fingerprint_command(b)

    def test_command_mutation_breaks_fingerprint(self, make_command):
        """§50: mutating parameters must produce a different fingerprint."""
        command = make_command()
        original = fingerprint_command(command)
        command.parameters["target"] = "different"
        current = fingerprint_command(command)
        assert original != current

    def test_fingerprint_covers_parameters(self, make_command):
        a = make_command(parameters={"severity": "normal"})
        b = make_command(parameters={"severity": "high"})
        assert fingerprint_command(a) != fingerprint_command(b)
