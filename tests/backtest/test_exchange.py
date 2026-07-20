import pytest

from services.backtest import (
    MatchingEngine,
    VirtualExchange,
    VirtualOrderBook,
    Fill,
    ExecutionReport,
    ExchangeService,
)


def test_matching():
    engine = MatchingEngine()

    assert engine.match(object()) is True


@pytest.mark.asyncio
async def test_virtual_exchange():
    exchange = VirtualExchange()

    order = object()

    result = await exchange.submit(order)

    assert result == order


def test_virtual_order_book():
    book = VirtualOrderBook()

    assert len(book.bids) == 0
    assert len(book.asks) == 0

    book.bids.append({"price": 100.0, "quantity": 10})
    book.asks.append({"price": 101.0, "quantity": 5})

    assert len(book.bids) == 1
    assert len(book.asks) == 1


def test_fill():
    fill = Fill(
        order_id="order-001",
        quantity=100.0,
        price=50.0,
    )

    assert fill.order_id == "order-001"
    assert fill.quantity == 100.0


def test_execution_report():
    report = ExecutionReport(
        order_id="order-002",
        status="FILLED",
        filled_quantity=50.0,
    )

    assert report.status == "FILLED"
    assert report.filled_quantity == 50.0


@pytest.mark.asyncio
async def test_exchange_service():
    service = ExchangeService()

    order = type("Order", (), {"id": "order-003", "quantity": 100.0})()

    report = await service.execute(order)

    assert report.order_id == "order-003"
    assert report.status == "FILLED"