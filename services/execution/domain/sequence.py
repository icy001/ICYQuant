from __future__ import annotations


class InvalidEventSequence(ValueError):
    pass


def validate_next_sequence(
    *,
    current_sequence: int,
    next_sequence: int,
) -> None:

    expected = current_sequence + 1

    if next_sequence != expected:
        raise InvalidEventSequence(
            f"expected sequence {expected}, "
            f"got {next_sequence}"
        )
