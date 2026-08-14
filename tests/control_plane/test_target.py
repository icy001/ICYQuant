"""Control target tests (Commit 29 Part 1.1 §10-11, §34).

A command must name its target explicitly, and an unknown target is rejected
(fail closed) instead of being "best-effort executed".
"""

import pytest

from services.control_plane.errors import TargetNotFound
from services.control_plane.target import (
    DEFAULT_CONTROL_TARGETS,
    ControlTarget,
    StaticTargetResolver,
)


class TestControlTarget:

    def test_target_defaults(self):
        target = ControlTarget(service="oms")
        assert target.service == "oms"
        assert target.instance is None
        assert target.environment == "production"

    def test_target_fields(self):
        target = ControlTarget(
            service="oms",
            instance="oms-primary",
            environment="production",
        )
        assert target.service == "oms"
        assert target.instance == "oms-primary"
        assert target.environment == "production"

    def test_target_is_frozen(self):
        target = ControlTarget(service="oms")
        with pytest.raises(Exception):
            target.service = "risk"  # type: ignore[misc]


class TestStaticTargetResolver:

    def test_resolves_known_production_target(self):
        resolver = StaticTargetResolver()
        target = ControlTarget(
            service="oms", instance="oms-primary", environment="production"
        )
        resolver.resolve(target)  # should not raise

    def test_rejects_unknown_instance_in_production(self):
        """§34 — production + an unlisted instance (e.g. test-oms) is rejected."""
        resolver = StaticTargetResolver()
        target = ControlTarget(
            service="oms", instance="test-oms", environment="production"
        )
        with pytest.raises(TargetNotFound):
            resolver.resolve(target)

    def test_rejects_unknown_service(self):
        resolver = StaticTargetResolver()
        target = ControlTarget(
            service="oms-unknown", instance="oms-primary", environment="production"
        )
        with pytest.raises(TargetNotFound):
            resolver.resolve(target)

    def test_rejects_unknown_environment(self):
        resolver = StaticTargetResolver()
        target = ControlTarget(
            service="oms", instance="oms-primary", environment="staging"
        )
        with pytest.raises(TargetNotFound):
            resolver.resolve(target)

    def test_fail_closed_for_every_unlisted_target(self):
        """§35 — anything not explicitly known is denied."""
        resolver = StaticTargetResolver()
        for target in [
            ControlTarget(service="oms"),
            ControlTarget(service="oms", instance="oms-dr-1"),
            ControlTarget(service="oms", environment="test"),
        ]:
            with pytest.raises(TargetNotFound):
                resolver.resolve(target)

    def test_custom_known_set(self):
        resolver = StaticTargetResolver(
            known={("staging", "oms", "oms-staging-01")}
        )
        resolver.resolve(
            ControlTarget(
                service="oms", instance="oms-staging-01", environment="staging"
            )
        )
        with pytest.raises(TargetNotFound):
            resolver.resolve(
                ControlTarget(
                    service="oms", instance="oms-primary", environment="production"
                )
            )

    def test_default_targets_only_cover_production(self):
        environments = {target[0] for target in DEFAULT_CONTROL_TARGETS}
        assert environments == {"production"}
