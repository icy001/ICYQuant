import pytest

from apps.api.dependencies import (
    get_database_session,
)


@pytest.mark.asyncio
async def test_dependency_exists():

    generator = get_database_session()

    assert generator