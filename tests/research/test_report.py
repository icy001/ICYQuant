from services.research import (
    ReportBuilder,
    ReportSection,
    ReportTemplate,
    ResearchReport,
    ReportService,
    ReportExporter,
)


def test_build_report():
    builder = ReportBuilder()

    report = builder.build(
        "Momentum Report",
        [
            ReportSection(
                title="Summary",
                content="Completed",
            )
        ],
    )

    assert report.title == "Momentum Report"
    assert len(report.sections) == 1


def test_report_section():
    section = ReportSection(
        title="Performance",
        content="Annual Return: 12%",
    )

    assert section.title == "Performance"
    assert section.content == "Annual Return: 12%"


def test_report_template():
    template = ReportTemplate(name="Standard", version="v1")

    assert template.name == "Standard"
    assert template.version == "v1"


def test_report_service():
    builder = ReportBuilder()
    service = ReportService(builder)

    report = service.generate(
        "Factor Report",
        [
            ReportSection("Introduction", "Factor research report"),
            ReportSection("Results", "Completed successfully"),
        ],
    )

    assert report.title == "Factor Report"
    assert len(report.sections) == 2


def test_report_exporter():
    exporter = ReportExporter()

    report = ResearchReport(
        title="Test Report",
        sections=[ReportSection("Section", "Content")],
    )

    result = exporter.export(report)

    assert result == report