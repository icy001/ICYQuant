from pathlib import Path


def test_alembic_structure():

    assert Path(
        "alembic/env.py"
    ).exists()

    assert Path(
        "alembic.ini"
    ).exists()


def test_migration_template():

    content = Path(
        "alembic/script.py.mako"
    ).read_text()

    assert (
        "upgrade"
        in
        content
    )

    assert (
        "downgrade"
        in
        content
    )