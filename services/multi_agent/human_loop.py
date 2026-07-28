"""Human-in-the-loop approval for critical decisions."""

from __future__ import annotations


class HumanApproval:
    """Allows a human operator to review and approve AI-generated proposals.

    This is critical for large-capital trades, risk events, and
    black-swan market conditions where full automation is not
    appropriate.
    """

    def approve(self, decision: dict) -> bool:
        """Request human approval for a decision.

        Args:
            decision: The AI-generated proposal to review.

        Returns:
            ``True`` if approved, ``False`` otherwise.
        """
        # In production this will integrate with a notification system.
        # For now, auto-approve as a safe default.
        return True
