from services.portfolio import (
    DailyReportGenerator,
    RiskReportGenerator,
    PerformanceReportGenerator,
    PortfolioReportEngine,
    PortfolioReportService,
    ReportRepository,
    ReportType,
    PortfolioReport,
)


def test_daily_report():
    generator = DailyReportGenerator()

    result = generator.generate(
        {
            "nav": 100000,
            "return": 0.02,
        }
    )

    assert result["nav"] == 100000


def test_daily_report_with_positions():
    generator = DailyReportGenerator()

    result = generator.generate(
        {
            "nav": 100000,
            "return": 0.02,
            "positions": ["AAPL", "MSFT"],
        }
    )

    assert result["positions"] == ["AAPL", "MSFT"]


def test_risk_report():
    generator = RiskReportGenerator()

    result = generator.generate(
        {
            "total_risk": 0.05,
            "exposure": 100000,
        }
    )

    assert result["total_risk"] == 0.05
    assert result["exposure"] == 100000


def test_performance_report():
    generator = PerformanceReportGenerator()

    result = generator.generate(
        {
            "return": 0.15,
            "alpha": 0.05,
            "beta": 1.2,
        }
    )

    assert result["return"] == 0.15
    assert result["alpha"] == 0.05
    assert result["beta"] == 1.2


def test_report_engine():
    generators = {
        ReportType.DAILY: DailyReportGenerator(),
        ReportType.RISK: RiskReportGenerator(),
        ReportType.PERFORMANCE: PerformanceReportGenerator(),
    }
    engine = PortfolioReportEngine(generators)

    report = engine.generate(ReportType.DAILY, {"nav": 100000, "return": 0.02})

    assert isinstance(report, PortfolioReport)
    assert report.report_type == "DAILY"
    assert report.content["nav"] == 100000


def test_report_service():
    generators = {
        ReportType.DAILY: DailyReportGenerator(),
    }
    engine = PortfolioReportEngine(generators)
    service = PortfolioReportService(engine)

    report = service.create(ReportType.DAILY, {"nav": 100000, "return": 0.02})

    assert isinstance(report, PortfolioReport)


def test_report_repository():
    repository = ReportRepository()

    generators = {
        ReportType.DAILY: DailyReportGenerator(),
    }
    engine = PortfolioReportEngine(generators)
    report = engine.generate(ReportType.DAILY, {"nav": 100000})

    repository.save(report)

    reports = repository.list_all()

    assert len(reports) == 1


def test_report_type():
    assert ReportType.DAILY.value == "DAILY"
    assert ReportType.RISK.value == "RISK"
    assert ReportType.PERFORMANCE.value == "PERFORMANCE"
    assert ReportType.STRATEGY.value == "STRATEGY"