from sqlalchemy import (
    inspect,
)

from services.database import (
    Base,
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)


class SampleModel(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "sample_model"


def test_base_model():
    mapper = inspect(
        SampleModel
    )

    columns = (
        mapper.columns.keys()
    )

    assert (
        "id"
        in
        columns
    )

    assert (
        "created_at"
        in
        columns
    )

    assert (
        "updated_at"
        in
        columns
    )

    assert (
        "deleted"
        in
        columns
    )