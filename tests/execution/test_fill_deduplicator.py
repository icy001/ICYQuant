import pytest

from services.execution.application.fill_deduplicator import (
    DuplicateFillError,
    FillDeduplicator,
)
from tests.execution.test_fill import (
    build_fill,
)


def test_duplicate_fill_is_rejected():

    deduplicator = FillDeduplicator()

    fill = build_fill(
        execution_id="fill-001"
    )

    deduplicator.check(fill)

    with pytest.raises(
        DuplicateFillError
    ):
        deduplicator.check(fill)
