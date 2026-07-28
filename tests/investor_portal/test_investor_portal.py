from services.investor_portal import *


def test_investor():
    investor = Investor(id="LP001", name="Test", status="active")
    service = InvestorAccountService()
    result = service.create(investor)
    assert result["account"] == "LP001"


def test_investor_dataclass():
    investor = Investor(id="LP002", name="Alpha Capital", status="active")
    assert investor.id == "LP002"
    assert investor.name == "Alpha Capital"
    assert investor.status == "active"


def test_investor_account_create():
    service = InvestorAccountService()
    investor = Investor(id="LP003", name="Beta Fund", status="pending")
    result = service.create(investor)
    assert result == {"account": "LP003"}


def test_investor_dashboard_view():
    dashboard = InvestorDashboard()
    data = {"nav": 100.0, "return": 0.15, "risk": 0.05}
    result = dashboard.view(data)
    assert result == {"dashboard": data}


def test_nav_view_display():
    view = NAVView()
    nav = 1050000.50
    result = view.display(nav)
    assert result == {"NAV": nav}


def test_performance_dashboard_analyze():
    dashboard = PerformanceDashboard()
    returns = {"total": 0.25, "alpha": 0.05, "beta": 0.12}
    result = dashboard.analyze(returns)
    assert result == {"return": returns}


def test_investor_risk_view():
    risk_view = InvestorRiskView()
    risk = {"var": 0.02, "drawdown": 0.08, "volatility": 0.12}
    result = risk_view.display(risk)
    assert result == {"risk": risk}


def test_report_center():
    center = ReportCenter()
    reports = center.list_reports()
    assert "monthly_report" in reports
    assert "risk_report" in reports
    assert len(reports) == 2


def test_investor_communication():
    comm = InvestorCommunication()
    result = comm.send("Your portfolio update is ready")
    assert result == {"status": "sent"}


def test_permission_manager():
    manager = PermissionManager()
    assert manager.check("LP") is True
    assert manager.check("Admin") is True
    assert manager.check("FundManager") is True
    assert manager.check("Auditor") is True


def test_investor_memory():
    memory = InvestorMemory()
    assert memory.history == []
    memory.save({"event": "login", "timestamp": "2024-01-01"})
    memory.save({"event": "report_access", "report": "monthly"})
    assert len(memory.history) == 2
    assert memory.history[0] == {"event": "login", "timestamp": "2024-01-01"}
    assert memory.history[1] == {"event": "report_access", "report": "monthly"}


def test_investor_portal_service():
    dashboard = InvestorDashboard()
    portal = InvestorPortalService(dashboard=dashboard)
    data = {"nav": 1500000.00, "performance": "+15.2%"}
    result = portal.open(data)
    assert result == {"dashboard": data}


def test_full_investor_portal_workflow():
    """End-to-end investor portal workflow."""
    # 1. Create investor
    investor = Investor(id="LP010", name="Omega Partners", status="active")
    account_svc = InvestorAccountService()
    account = account_svc.create(investor)
    assert account["account"] == "LP010"

    # 2. Dashboard view
    dashboard = InvestorDashboard()
    dashboard_data = {
        "nav": 10_000_000.00,
        "return": {"ytd": 0.18, "since_inception": 0.45},
        "risk": {"var": 0.03, "drawdown": 0.06},
    }
    result = dashboard.view(dashboard_data)
    assert result["dashboard"] == dashboard_data

    # 3. NAV view
    nav_view = NAVView()
    nav_result = nav_view.display(10_000_000.00)
    assert nav_result["NAV"] == 10_000_000.00

    # 4. Performance
    perf = PerformanceDashboard()
    perf_result = perf.analyze({"total_return": 0.18, "alpha": 0.04})
    assert perf_result["return"]["total_return"] == 0.18

    # 5. Risk view
    risk_view = InvestorRiskView()
    risk_result = risk_view.display({"drawdown": 0.06, "volatility": 0.11})
    assert risk_result["risk"]["drawdown"] == 0.06

    # 6. Reports
    report_center = ReportCenter()
    reports = report_center.list_reports()
    assert len(reports) == 2

    # 7. Communication
    comm = InvestorCommunication()
    msg = comm.send("Quarterly report is available")
    assert msg["status"] == "sent"

    # 8. Permissions
    perm = PermissionManager()
    assert perm.check("LP") is True

    # 9. Memory
    memory = InvestorMemory()
    memory.save({"action": "portal_login"})
    memory.save({"action": "view_performance"})
    assert len(memory.history) == 2

    # 10. Portal service
    portal = InvestorPortalService(dashboard=dashboard)
    portal_result = portal.open({"nav": 10_000_000.00})
    assert portal_result["dashboard"] == {"nav": 10_000_000.00}
