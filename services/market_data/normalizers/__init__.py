"""Market data normalizer package (Commit 014 §9).

A normalizer turns a *vendor-specific* payload into the ICYQuant
standard model.  It performs parsing, field mapping, type conversion,
exchange detection and timestamp conversion — and nothing else.  It
never applies business judgement: a syntactically valid but
semantically wrong value (``last = -1``) is mapped faithfully and
handed to the Commit 006 Quality Gate.

Import surface::

    from services.market_data.normalizers import BrokerQuoteNormalizer
"""
from __future__ import annotations

from .broker_quote_normalizer import BrokerQuoteNormalizer, normalize_symbol

__all__ = ["BrokerQuoteNormalizer", "normalize_symbol"]
