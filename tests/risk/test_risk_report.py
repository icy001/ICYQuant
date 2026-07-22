from services.risk import (
    DailyRiskReportGenerator,
)


def test_daily_risk_report():
    generator = DailyRiskReportGenerator()

    result = generator.generate(
        {
            "risk_score": 0.36,
            "metrics": {
                "VAR": 0.21
            },
            "alerts": [
                "Liquidity Warning"
            ],
        }
    )

    assert result["risk_score"] == 0.36