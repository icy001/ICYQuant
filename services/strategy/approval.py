"""
Signal approval workflow.
"""

from __future__ import annotations


class SignalApprovalService:
    def __init__(
        self,
        pipeline,
    ):
        self.pipeline = pipeline

    async def approve(
        self,
        signal,
    ):
        valid = await self.pipeline.validate(signal)
        if not valid:
            return None
        return signal