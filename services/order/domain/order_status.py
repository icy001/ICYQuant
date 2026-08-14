"""Order lifecycle status (Commit 33 Part 1.1).

The order status answers *"what has happened to this order in its trading
lifecycle?"* - a different question from the order request state (Commit 32),
which asks *"has the request reached the OMS yet?"*:

.. code-block:: text

    Order Request (Commit 32)          Order (Commit 33)
    CREATED                            CREATED
    VALIDATED                          PENDING_SUBMIT
    NORMALIZED                         SUBMITTED
    SUBMITTED                          ACCEPTED
    ACCEPTED                           PARTIALLY_FILLED
    HANDOFF                            FILLED / CANCELLED / REJECTED / EXPIRED
"""

from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    """Lifecycle status of an OMS order."""

    CREATED = "CREATED"
    PENDING_SUBMIT = "PENDING_SUBMIT"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
