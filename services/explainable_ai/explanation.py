"""Human Explanation Generator – produces trader-readable explanations."""

from typing import Any, Dict, List, Optional


class HumanExplanationGenerator:
    """Generates human-readable explanations from AI decisions and attribution data."""

    def generate(self, signal: str) -> str:
        """Generate a simple explanation for a trading signal.

        Args:
            signal: the trading signal (e.g. "BUY", "SELL").

        Returns:
            Human-readable explanation string.
        """
        return f"AI recommends {signal}"

    def generate_detailed(
        self,
        signal: str,
        symbol: Optional[str] = None,
        attribution: Optional[Dict[str, float]] = None,
        confidence: Optional[float] = None,
        reasons: Optional[List[str]] = None,
        risk_level: Optional[str] = None,
    ) -> str:
        """Generate a rich, trader-friendly explanation.

        Args:
            signal: trading signal.
            symbol: instrument symbol.
            attribution: module contribution map.
            confidence: confidence score (0-100).
            reasons: list of human-readable reasons.
            risk_level: risk assessment label.

        Returns:
            Multi-line explanation string.
        """
        target = f" {symbol}" if symbol else ""
        lines = [f"建议{signal}{target}。"]

        if reasons:
            lines.append("")
            lines.append("原因：")
            for reason in reasons:
                lines.append(f"  - {reason}")

        if attribution:
            lines.append("")
            lines.append("信号归因：")
            sorted_attr = sorted(attribution.items(), key=lambda x: x[1], reverse=True)
            for module, contrib in sorted_attr:
                lines.append(f"  - {module}: {contrib:.0%}")

        if confidence is not None:
            lines.append("")
            lines.append(f"置信度：{confidence:.0f}%")

        if risk_level is not None:
            lines.append(f"风险等级：{risk_level}")

        return "\n".join(lines)

    def generate_brief(self, signal: str, confidence: float, reason: str) -> str:
        """Generate a one-line summary."""
        return f"{signal} (置信度 {confidence:.0f}%) — {reason}"
