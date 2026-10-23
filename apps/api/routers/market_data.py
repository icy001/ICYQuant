"""Market Data API — the single standard entry point (Commit 010).

Seven endpoint groups, mounted at ``/api/market-data``::

    GET  /instruments              Universe (§2)
    GET  /instruments/{symbol}     One instrument
    GET  /quotes/{symbol}          Latest quote + quality (§3)
    GET  /quotes?symbols=a,b,c     Batch quotes (§4)
    GET  /bars?symbol=&timeframe=  Unified 1m series (§5/§6/§7)
    GET  /session                  Current market phase (§8)
    GET  /sessions                 Both exchanges
    GET  /quality/{symbol}         Quality Gate verdict (§9)
    GET  /quality                  Universe quality roll-up
    GET  /health                   System health (§10)
    GET  /wiring                   §15 topology diagnostic
    POST /feed/start | /feed/stop  Ingestion lifecycle (OPERATOR/ADMIN)

Design rules honoured here:

* **Routes do no data work.**  They parse/validate HTTP input, call
  :class:`~services.market_data.market_data_service.MarketDataService`
  and serialise a Pydantic model (§11).  No route touches Redis, the
  adapter or the merge engine.
* **Quality is never bypassed** (§14).  Every quote/bar payload carries
  its gate verdict, so a STALE quote is served *as* STALE.
* **Errors are typed** (§13): 400 malformed parameter, 404 unknown
  symbol / no data yet, 503 pipeline unavailable.  Type-coercion
  failures (``limit=abc``) keep FastAPI's standard 422 — those never
  reach the service.
* **Reads may start ingestion lazily** — the first data read boots the
  quote feed so a cold process serves real data instead of an empty
  shell.  ``/health`` deliberately does **not**: a probe must not
  mutate state.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from apps.api.schemas.market_data import (
    BarSeriesResponse,
    ErrorResponse,
    HealthResponse,
    InstrumentListResponse,
    InstrumentResponse,
    MarketDataWiringResponse,
    QualityOverviewResponse,
    QualityResponse,
    QuoteListResponse,
    QuoteResponse,
    SessionListResponse,
    SessionResponse,
)
from apps.dashboard.auth import Principal, require_roles
from services.market_data.market_data_service import (
    MAX_BARS,
    MIN_BARS,
    MarketDataServiceError,
    SUPPORTED_TIMEFRAMES,
    market_data_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-data", tags=["market-data"])

_ERROR_RESPONSES: dict = {
    400: {"model": ErrorResponse, "description": "Invalid parameter"},
    404: {"model": ErrorResponse, "description": "Unknown symbol / no data"},
    503: {"model": ErrorResponse, "description": "Pipeline unavailable"},
}


def market_data_error_handler(request, exc: MarketDataServiceError):
    """Render :class:`MarketDataServiceError` as the §13 envelope.

    Registered on the app in ``apps/api/main.py`` so that any future
    market-data route inherits the same error contract.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.as_dict(),
    )


def _service() -> object:
    """Single shared service instance (§15)."""
    return market_data_service


# ══════════════════════════════════════════════════════════════════
# ① Instruments
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/instruments",
    response_model=InstrumentListResponse,
    responses=_ERROR_RESPONSES,
    summary="Trading universe",
)
def list_instruments(
    exchange: Optional[str] = Query(
        None, description="Filter by exchange: SZSE | SSE"
    ),
    instrument_type: Optional[str] = Query(
        None, description="Filter by type: ETF | QDII-ETF | LOF | QDII-LOF"
    ),
    enabled: Optional[bool] = Query(
        None, description="Filter by enabled flag"
    ),
    symbol: Optional[str] = Query(
        None, description="Filter to a single symbol"
    ),
    principal: Principal = Depends(require_roles()),
):
    """Current universe with optional filters (§2).

    An unknown ``exchange`` / ``instrument_type`` / ``symbol`` is a
    **400/404**, never a silently empty list (§13).
    """
    return _service().instruments(
        symbol=symbol,
        exchange=exchange,
        instrument_type=instrument_type,
        enabled=enabled,
    )


@router.get(
    "/instruments/{symbol}",
    response_model=InstrumentResponse,
    responses=_ERROR_RESPONSES,
    summary="One instrument",
)
def get_instrument(
    symbol: str,
    principal: Principal = Depends(require_roles()),
):
    return _service().instrument(symbol)


# ══════════════════════════════════════════════════════════════════
# ② / ③ / ④ Quotes
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/quotes",
    response_model=QuoteListResponse,
    responses=_ERROR_RESPONSES,
    summary="Batch quotes",
)
def get_quotes(
    symbols: Optional[str] = Query(
        None,
        description=(
            "Comma-separated symbols, e.g. 159852,513050. "
            "Omit for the whole enabled universe (§4)"
        ),
    ),
    principal: Principal = Depends(require_roles()),
):
    """Batch quotes — Dashboards must not loop one symbol at a time."""
    wanted = None
    if symbols is not None:
        wanted = [s for s in (part.strip() for part in symbols.split(",")) if s]
    service = _service()
    service.ensure_feed()
    return service.quotes(wanted)


@router.get(
    "/quotes/{symbol}",
    response_model=QuoteResponse,
    responses=_ERROR_RESPONSES,
    summary="Latest quote",
)
def get_quote(
    symbol: str,
    principal: Principal = Depends(require_roles()),
):
    """Latest quote plus quality / age / latency (§3, §14).

    A registered symbol with no data yet is reported honestly as
    ``status=OFFLINE`` with ``last=null`` and ``quality=null`` — the
    API never dresses absence up as a price.
    """
    service = _service()
    service.ensure_feed()
    return service.quote(symbol)


# ══════════════════════════════════════════════════════════════════
# ⑤ / ⑥ / ⑦ Bars
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/bars",
    response_model=BarSeriesResponse,
    responses=_ERROR_RESPONSES,
    summary="Unified 1m bars",
)
def get_bars(
    symbol: str = Query(..., description="Instrument symbol, e.g. 159852"),
    timeframe: str = Query(
        "1m",
        description=f"Only {list(SUPPORTED_TIMEFRAMES)} is supported",
    ),
    limit: Optional[int] = Query(
        None, description=f"Between {MIN_BARS} and {MAX_BARS} (default 200)"
    ),
    start: Optional[str] = Query(
        None, description="Inclusive ISO-8601 lower bound"
    ),
    end: Optional[str] = Query(
        None, description="Inclusive ISO-8601 upper bound"
    ),
    principal: Principal = Depends(require_roles()),
):
    """One merged historical + realtime 1m series (§5/§6).

    The caller never stitches two sources together, and the in-progress
    minute is always flagged ``is_closed=false`` (§7).
    """
    return _service().bars(
        symbol,
        timeframe,
        limit if limit is not None else 200,
        start=start,
        end=end,
    )


# ══════════════════════════════════════════════════════════════════
# ⑧ Session
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/session",
    response_model=SessionResponse,
    responses=_ERROR_RESPONSES,
    summary="Current market phase",
)
def get_session(
    exchange: str = Query("SZSE", description="SZSE | SSE"),
    principal: Principal = Depends(require_roles()),
):
    """Current phase + ``is_tradable`` (§8).

    Dashboard / Strategy read ``is_tradable`` instead of re-deriving
    "is the market open right now?".
    """
    return _service().session(exchange)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    responses=_ERROR_RESPONSES,
    summary="Both exchanges",
)
def get_sessions(
    principal: Principal = Depends(require_roles()),
):
    return _service().sessions()


# ══════════════════════════════════════════════════════════════════
# ⑨ Quality
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/quality",
    response_model=QualityOverviewResponse,
    responses=_ERROR_RESPONSES,
    summary="Universe quality roll-up",
)
def get_quality_overview(
    limit: int = Query(
        0, description="Include the N most recent quarantined payloads"
    ),
    principal: Principal = Depends(require_roles()),
):
    service = _service()
    service.ensure_feed()
    return service.quality_overview(limit=max(0, limit))


@router.get(
    "/quality/{symbol}",
    response_model=QualityResponse,
    responses=_ERROR_RESPONSES,
    summary="Quality verdict for one symbol",
)
def get_quality(
    symbol: str,
    principal: Principal = Depends(require_roles()),
):
    """Quality Gate verdict (§9), with ``checks`` labelled PASS/FAIL.

    404 when the symbol exists but nothing has been received yet —
    there is no verdict to report.
    """
    service = _service()
    service.ensure_feed()
    return service.quality(symbol)


# ══════════════════════════════════════════════════════════════════
# ⑩ Health
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Market data health",
)
def get_health(
    principal: Principal = Depends(require_roles()),
):
    """Adapter / Redis / quality roll-up plus the overall verdict (§10).

    Non-mutating: it never starts the feed, so it is safe to poll.
    ``feed.started=false`` distinguishes "never started" from "down".
    """
    return _service().health()


@router.get(
    "/wiring",
    response_model=MarketDataWiringResponse,
    summary="§15 topology diagnostic",
)
def get_wiring(
    principal: Principal = Depends(require_roles()),
):
    """Proof that Paper Trading and the API share one service (§15).

    Paper Trading is an **in-process** consumer — it never goes over
    HTTP to reach market data in the same process.
    """
    return _service().wiring()


# ══════════════════════════════════════════════════════════════════
# Ingestion lifecycle (operator actions)
# ══════════════════════════════════════════════════════════════════


@router.post(
    "/feed/start",
    responses=_ERROR_RESPONSES,
    summary="Start (or restart) ingestion",
)
def start_feed(
    response: Response,
    restart: bool = Query(False, description="Restart a running feed"),
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
):
    service = _service()
    stats = service.restart_feed() if restart else service.ensure_feed()
    response.status_code = 202 if restart else 200
    return {
        "running": service.feed_running,
        "started": service.feed_started,
        "restarted": bool(restart),
        "adapter": service.adapter_name,
        "stats": stats,
    }


@router.post(
    "/feed/stop",
    responses=_ERROR_RESPONSES,
    summary="Stop ingestion",
)
def stop_feed(
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
):
    service = _service()
    result = service.stop_feed()
    return {
        "running": False,
        "started": service.feed_started,
        "adapter": service.adapter_name,
        "stats": result,
    }


__all__ = ["router", "market_data_error_handler"]
