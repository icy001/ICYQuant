"""
Reconciliation REST API.
"""

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
)

from pydantic import (
    BaseModel,
)

from apps.api.dependencies import (
    get_reconciliation_engine,
)


router = APIRouter(
    prefix="/reconciliation",
    tags=[
        "reconciliation"
    ]
)


class ReconcileRequest(
    BaseModel
):
    internal: dict
    external: dict


class DifferenceResponse(
    BaseModel
):
    symbol: Optional[str]
    delta: str
    message: str


@router.post(
    "/check",
    response_model=list[DifferenceResponse],
)
def reconcile(
    request: ReconcileRequest,
    engine=Depends(
        get_reconciliation_engine
    )
):
    differences = (
        engine.reconcile_positions(
            request.internal,
            request.external
        )
    )

    return [
        DifferenceResponse(
            symbol=d.symbol,
            delta=str(
                d.delta
            ),
            message=d.message
        )
        for d in differences
    ]


@router.get(
    "/health"
)
def health():
    return {
        "service":
        "reconciliation",
        "status":
        "UP"
    }