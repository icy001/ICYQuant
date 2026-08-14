"""Order identity hierarchy (Commit 33 Part 1.1).

.. code-block:: text

    Order Request ID        OR-20260813-000001
        -> Order ID         ORD-20260813-000001
        -> Client Order ID  ICY-ORD-20260813-000001
        -> Venue Order ID   (adapter owned)
        -> Execution ID     EXEC-20260813-000001

This part defines the OMS-internal order id generator plus the reserved client
and execution id generators; venue ids are owned by the broker/exchange
adapters.  The chain answers *"which real market order corresponds to this
strategy trade?"*.
"""

from __future__ import annotations

import itertools
import time
from datetime import datetime
from typing import Optional

_order_counter = itertools.count(1)
_client_order_counter = itertools.count(1)
_execution_counter = itertools.count(1)
_execution_request_counter = itertools.count(1)
_event_counter = itertools.count(1)

#: Prefix for OMS-internal order ids.
ORDER_ID_PREFIX = "ORD"
#: Prefix for client order ids (reserved for OMS/broker/exchange correlation).
CLIENT_ORDER_ID_PREFIX = "ICY-ORD"
#: Prefix for execution ids (reserved for fill handling).
EXECUTION_ID_PREFIX = "EXEC"
#: Prefix for execution request ids (Commit 33 Part 1.3).
EXECUTION_REQUEST_ID_PREFIX = "EXREQ"
#: Prefix for order domain event ids (Commit 33 Part 1.4).
EVENT_ID_PREFIX = "EVT-ORD"


def _date_part(timestamp: Optional[float]) -> str:
    reference = time.time() if timestamp is None else timestamp
    return datetime.fromtimestamp(reference).strftime("%Y%m%d")


def new_order_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic OMS order id, e.g. ``ORD-20260813-000001``."""
    return f"{ORDER_ID_PREFIX}-{_date_part(timestamp)}-{next(_order_counter):06d}"


def new_client_order_id(timestamp: Optional[float] = None) -> str:
    """Generate a client order id, e.g. ``ICY-ORD-20260813-000001``."""
    return (
        f"{CLIENT_ORDER_ID_PREFIX}-{_date_part(timestamp)}-"
        f"{next(_client_order_counter):06d}"
    )


def new_execution_id(timestamp: Optional[float] = None) -> str:
    """Generate an execution id, e.g. ``EXEC-20260813-000001`` (reserved)."""
    return (
        f"{EXECUTION_ID_PREFIX}-{_date_part(timestamp)}-"
        f"{next(_execution_counter):06d}"
    )


def new_execution_request_id(timestamp: Optional[float] = None) -> str:
    """Generate an execution request id, e.g. ``EXREQ-20260813-000001``.

    Every submission / cancel / retry attempt has its own execution request id
    so one order can legitimately have many execution requests (Commit 33 Part
    1.3 #18).
    """
    return (
        f"{EXECUTION_REQUEST_ID_PREFIX}-{_date_part(timestamp)}-"
        f"{next(_execution_request_counter):06d}"
    )


def new_event_id() -> str:
    """Generate a monotonic order event id, e.g. ``EVT-ORD-000001``.

    Event ids are distinct from order ids: one order emits many events, and
    audit / reconciliation / trade-book key on the event stream (Commit 33 Part
    1.4 #4).
    """
    return f"{EVENT_ID_PREFIX}-{next(_event_counter):06d}"
