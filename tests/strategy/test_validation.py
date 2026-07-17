import pytest

from services.strategy import (
    DuplicateSignalValidator,
    RiskSignalValidator,
    SignalApprovalService,
    SignalValidationPipeline,
    SignalGenerator,
    SignalType,
)


@pytest.mark.asyncio
async def test_signal_validation():
    generator = SignalGenerator()

    signal = generator.generate(
        strategy_id="demo",
        symbol="AAPL",
        signal=SignalType.BUY,
        confidence=0.9,
        reason="test",
    )

    pipeline = SignalValidationPipeline(
        [
            DuplicateSignalValidator(),
            RiskSignalValidator(),
        ]
    )

    service = SignalApprovalService(pipeline)

    result = await service.approve(signal)

    assert result is not None


@pytest.mark.asyncio
async def test_signal_rejected_low_confidence():
    generator = SignalGenerator()

    signal = generator.generate(
        strategy_id="demo",
        symbol="MSFT",
        signal=SignalType.SELL,
        confidence=0.3,
        reason="low confidence",
    )

    pipeline = SignalValidationPipeline(
        [
            RiskSignalValidator(),
        ]
    )

    service = SignalApprovalService(pipeline)

    result = await service.approve(signal)

    assert result is None


@pytest.mark.asyncio
async def test_duplicate_signal_rejected():
    generator = SignalGenerator()

    signal1 = generator.generate(
        strategy_id="demo",
        symbol="GOOG",
        signal=SignalType.BUY,
        confidence=0.8,
        reason="first",
    )

    signal2 = generator.generate(
        strategy_id="demo",
        symbol="GOOG",
        signal=SignalType.BUY,
        confidence=0.8,
        reason="second",
    )

    duplicate_validator = DuplicateSignalValidator()

    result1 = await duplicate_validator.validate(signal1)
    result2 = await duplicate_validator.validate(signal2)

    assert result1 is True
    assert result2 is False