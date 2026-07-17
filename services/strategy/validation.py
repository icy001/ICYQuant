"""
Signal validation pipeline.
"""

from __future__ import annotations


class SignalValidationPipeline:
    def __init__(
        self,
        validators: list,
    ):
        self.validators = validators

    async def validate(
        self,
        signal,
    ) -> bool:
        for validator in self.validators:
            result = await validator.validate(signal)
            if not result:
                return False
        return True