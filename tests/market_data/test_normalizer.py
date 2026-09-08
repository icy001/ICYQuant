"""Tests for QuoteNormalizer — multi-source format normalization.

Commit 003 gate: 11/11 symbol parsing, 11/11 symbol normalization,
11/11 exchange normalization.
"""
from __future__ import annotations

import pytest

from services.market_data.domain.instrument import Exchange
from services.market_data.exceptions.market_data_error import (
    InvalidSymbolError,
)
from services.market_data.normalizer import (
    QuoteNormalizer,
    normalize_exchange,
    normalize_symbol,
)

SEED_SYMBOLS = [
    "159852", "513050", "159890", "159559", "159569",
    "515880", "159871", "513310", "501225", "161116", "165520",
]


class TestSymbolNormalization:
    """11/11 bare symbols parse and infer exchange."""

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_bare_symbol(self, symbol):
        sym, ex = normalize_symbol(symbol)
        assert sym == symbol
        if symbol.startswith(("15", "16")):
            assert ex == Exchange.SZSE
        else:
            assert ex == Exchange.SSE

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_suffixed_symbol_sz_sh(self, symbol):
        """Source A format: 159852.SZ / 513050.SH"""
        suffix = "SZ" if symbol.startswith(("15", "16")) else "SH"
        sym, ex = normalize_symbol(f"{symbol}.{suffix}")
        assert sym == symbol
        assert ex == (Exchange.SZSE if suffix == "SZ" else Exchange.SSE)

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_suffixed_symbol_full_name(self, symbol):
        """Variant: 159852.SZSE / 513050.SSE"""
        full = "SZSE" if symbol.startswith(("15", "16")) else "SSE"
        sym, ex = normalize_symbol(f"{symbol}.{full}")
        assert sym == symbol
        assert ex.value == full

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_prefixed_symbol(self, symbol):
        """Source C format: SZ159852 / SH513050"""
        prefix = "SZ" if symbol.startswith(("15", "16")) else "SH"
        sym, ex = normalize_symbol(f"{prefix}{symbol}")
        assert sym == symbol
        assert ex == (Exchange.SZSE if prefix == "SZ" else Exchange.SSE)

    def test_lowercase_input(self):
        sym, ex = normalize_symbol("sz159852")
        assert sym == "159852"
        assert ex == Exchange.SZSE

    def test_whitespace_stripped(self):
        sym, ex = normalize_symbol("  159852  ")
        assert sym == "159852"
        assert ex == Exchange.SZSE


class TestSymbolRejection:
    def test_empty_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("")

    def test_none_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol(None)

    def test_non_string_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol(159852)

    def test_wrong_length_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("15985")

    def test_non_digit_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("1598AB")

    def test_unknown_prefix_rejected(self):
        # 30xxxx is ChiNext stock, not a fund
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("300001")

    def test_bad_suffix_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("159852.XX")

    def test_unknown_letter_prefix_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("XX159852")


class TestExchangeNormalization:
    """All accepted spellings map to SSE / SZSE — never SH + SSE mixed."""

    def test_sse_aliases(self):
        for raw in ("SSE", "sse", "SH", "sh", "SHA", "Shanghai", "上海", "上交所"):
            assert normalize_exchange(raw) == Exchange.SSE, raw

    def test_szse_aliases(self):
        for raw in ("SZSE", "szse", "SZ", "sz", "SHE", "Shenzhen", "深圳", "深交所"):
            assert normalize_exchange(raw) == Exchange.SZSE, raw

    def test_enum_passthrough(self):
        assert normalize_exchange(Exchange.SSE) == Exchange.SSE
        assert normalize_exchange(Exchange.SZSE) == Exchange.SZSE

    def test_unknown_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_exchange("NYSE")

    def test_none_rejected(self):
        with pytest.raises(InvalidSymbolError):
            normalize_exchange(None)


class TestQuoteNormalizerClass:
    def test_normalize_inferred(self):
        n = QuoteNormalizer()
        sym, ex = n.normalize("159852.SZ")
        assert (sym, ex) == ("159852", Exchange.SZSE)

    def test_normalize_explicit_exchange_wins(self):
        n = QuoteNormalizer()
        sym, ex = n.normalize("159852", "SZSE")
        assert (sym, ex) == ("159852", Exchange.SZSE)

    def test_normalize_all_seeds(self):
        n = QuoteNormalizer()
        results = n.normalize_all(SEED_SYMBOLS)
        assert len(results) == 11
        for (sym, ex) in results:
            assert len(sym) == 6
            assert ex in (Exchange.SSE, Exchange.SZSE)
