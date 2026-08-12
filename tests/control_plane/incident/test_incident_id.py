"""Unit tests: IncidentId format, generation and serialization."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.incident.incident_id import IncidentId

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


class TestIncidentIdFormat:
    def test_accepts_valid_id(self):
        iid = IncidentId("INC-20260812-000001")
        assert iid.value == "INC-20260812-000001"

    def test_rejects_missing_prefix(self):
        with pytest.raises(ValueError):
            IncidentId("20260812-000001")

    def test_rejects_bad_date(self):
        with pytest.raises(ValueError):
            IncidentId("INC-2026812-000001")

    def test_rejects_short_sequence(self):
        with pytest.raises(ValueError):
            IncidentId("INC-20260812-1")

    def test_rejects_non_string(self):
        with pytest.raises(TypeError):
            IncidentId(12345)  # type: ignore[arg-type]

    def test_strips_whitespace(self):
        assert IncidentId("  INC-20260812-000002  ").value == "INC-20260812-000002"


class TestIncidentIdGeneration:
    def test_generate_uses_date_and_sequence(self):
        iid = IncidentId.generate(seq=42, occurred_at=NOW)
        assert iid.value == "INC-20260812-000042"

    def test_generate_pads_sequence_to_six_digits(self):
        assert IncidentId.generate(seq=7, occurred_at=NOW).value == "INC-20260812-000007"

    def test_generate_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            IncidentId.generate(seq=1_000_000, occurred_at=NOW)


class TestIncidentIdComparison:
    def test_equal_ids_compare_equal(self):
        assert IncidentId("INC-20260812-000001") == IncidentId("INC-20260812-000001")

    def test_different_ids_compare_unequal(self):
        assert IncidentId("INC-20260812-000001") != IncidentId("INC-20260812-000002")

    def test_hashable(self):
        assert hash(IncidentId("INC-20260812-000001")) == hash(IncidentId("INC-20260812-000001"))

    def test_string_conversion(self):
        assert str(IncidentId("INC-20260812-000001")) == "INC-20260812-000001"


class TestIncidentIdSerialization:
    def test_round_trip(self):
        iid = IncidentId("INC-20260812-000001")
        assert IncidentId.from_dict(iid.to_dict()) == iid
