"""
Backpressure policies.

Defines the policies for handling
backpressure when the logging queue
is full, determining whether to block,
drop records, or buffer in memory.
"""

from __future__ import annotations

from enum import Enum


class BackpressurePolicy(Enum):
    """
    Backpressure policy enum.

    Determines behavior when the log
    queue reaches capacity:

    - BLOCK: Block the producer until space is available
    - DROP_NEWEST: Drop the incoming record
    - DROP_OLDEST: Remove the oldest record to make space
    - MEMORY_BUFFER: Spill to memory buffer
    """

    BLOCK = "block"
    DROP_NEWEST = "drop_newest"
    DROP_OLDEST = "drop_oldest"
    MEMORY_BUFFER = "memory_buffer"
