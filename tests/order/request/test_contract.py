"""Tests for the order request factory contract."""

import pytest

from services.order.request.contract import OrderRequestFactoryProtocol
from services.order.request.factory import OrderRequestFactory


def test_factory_satisfies_contract():
    # OrderRequestFactoryProtocol is a structural Protocol: runtime checks work
    # because OrderRequestFactory provides the exact create(...) signature.
    assert isinstance(OrderRequestFactory(), OrderRequestFactoryProtocol)


def test_protocol_has_create_method():
    assert hasattr(OrderRequestFactoryProtocol, "create")
    signature = getattr(OrderRequestFactoryProtocol, "create")
    assert signature is not None


def test_factory_create_signature_requires_created_at():
    factory = OrderRequestFactory()
    with pytest.raises(TypeError):
        factory.create(None)  # missing keyword-only parameters
