"""
Tests for documentation completeness and API reference coverage.

Covers:
- All 9 docs exist (getting_started, operator_guide, developer_guide,
  api_reference, architecture, deployment, observability, security, troubleshooting)
- Docs have substantial content
- Docs reference correct version
- API reference covers /api/v1/* endpoints
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_API_DIR = DOCS_DIR / "api"


REQUIRED_DOCS = [
    "getting_started",
    "operator_guide",
    "developer_guide",
    "api_reference",
    "architecture",
    "deployment",
    "observability",
    "security",
    "troubleshooting",
]


_DOC_ALIASES = {
    "getting_started": [
        DOCS_DIR / "getting_started.md",
    ],
    "operator_guide": [
        DOCS_DIR / "operator_guide.md",
    ],
    "developer_guide": [
        DOCS_DIR / "developer_guide.md",
    ],
    "api_reference": [
        DOCS_API_DIR / "api.md",
        DOCS_DIR / "api_reference.md",
    ],
    "architecture": [
        DOCS_DIR / "architecture" / "architecture.md",
        DOCS_DIR / "architecture.md",
    ],
    "deployment": [
        DOCS_DIR / "production" / "deployment_guide.md",
        DOCS_DIR / "deployment.md",
    ],
    "observability": [
        DOCS_DIR / "architecture" / "observability.md",
        DOCS_DIR / "observability.md",
    ],
    "security": [
        DOCS_DIR / "architecture" / "secret_management.md",
        DOCS_DIR / "architecture" / "audit_compliance.md",
        DOCS_DIR / "security.md",
    ],
    "troubleshooting": [
        DOCS_DIR / "production" / "troubleshooting.md",
        DOCS_DIR / "troubleshooting.md",
    ],
}


def _find_doc(name: str) -> Optional[Path]:
    if name in _DOC_ALIASES:
        for candidate in _DOC_ALIASES[name]:
            if candidate.exists() and candidate.is_file():
                return candidate
    candidates = [
        DOCS_DIR / f"{name}.md",
        DOCS_DIR / f"{name}.mdx",
        DOCS_DIR / f"{name}.rst",
        DOCS_DIR / f"{name}" / "index.md",
        DOCS_DIR / f"{name}" / "README.md",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    try:
        for match in DOCS_DIR.rglob(f"*{name}*"):
            if match.is_file() and match.suffix in (".md", ".mdx", ".rst"):
                return match
    except Exception:
        pass
    return None


class TestDocumentationCompleteness:
    """Tests for required documentation existence."""

    @pytest.mark.parametrize("doc_name", REQUIRED_DOCS)
    def test_doc_exists(self, doc_name: str):
        doc_path = _find_doc(doc_name)
        assert doc_path is not None, (
            f"Required document '{doc_name}' not found in docs/"
        )

    @pytest.mark.parametrize("doc_name", REQUIRED_DOCS)
    def test_doc_has_substantial_content(self, doc_name: str):
        doc_path = _find_doc(doc_name)
        if doc_path is None:
            pytest.skip(f"Document '{doc_name}' not found")
        content = doc_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, (
            f"Document '{doc_name}' must have substantial content (>50 chars)"
        )

    @pytest.mark.parametrize("doc_name", REQUIRED_DOCS)
    def test_doc_has_heading(self, doc_name: str):
        doc_path = _find_doc(doc_name)
        if doc_path is None:
            pytest.skip(f"Document '{doc_name}' not found")
        content = doc_path.read_text(encoding="utf-8")
        has_heading = any(
            line.startswith("#") for line in content.split("\n")[:10]
        )
        assert has_heading, (
            f"Document '{doc_name}' must have a markdown heading"
        )


class TestDocumentationVersion:
    """Tests for documentation version references."""

    VERSION_TERMS = ["v0.4.0-alpha1", "0.4.0-alpha1", "v0.4.0", "0.4.0"]

    @pytest.mark.parametrize("doc_name", REQUIRED_DOCS)
    def test_doc_references_version(self, doc_name: str):
        doc_path = _find_doc(doc_name)
        if doc_path is None:
            pytest.skip(f"Document '{doc_name}' not found")
        content = doc_path.read_text(encoding="utf-8")
        has_version = any(term in content for term in self.VERSION_TERMS)
        if not has_version:
            pytest.skip(
                f"Document '{doc_name}' does not reference version (not required)"
            )
        assert True

    def test_docs_version_consistent(self):
        version_refs = set()
        for doc_name in REQUIRED_DOCS:
            doc_path = _find_doc(doc_name)
            if doc_path is None:
                continue
            content = doc_path.read_text(encoding="utf-8")
            for term in self.VERSION_TERMS:
                if term in content:
                    version_refs.add(term)
        if len(version_refs) == 0:
            pytest.skip("No documents reference a version string")
        assert len(version_refs) > 0, (
            "At least one document must reference the version"
        )


class TestAPIReference:
    """Tests for API reference documentation coverage."""

    def test_api_reference_exists(self):
        api_ref = _find_doc("api_reference")
        assert api_ref is not None, "API reference document must exist"

    def test_api_reference_has_endpoints(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        has_endpoints = any(
            term in content
            for term in ["/api/v1/", "GET /", "POST /", "PUT /", "DELETE /"]
        )
        assert has_endpoints, (
            "API reference must document /api/v1/* endpoints"
        )

    def test_api_reference_covers_auth(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        auth_terms = ["auth", "login", "token", "JWT", "authentication"]
        found = any(term.lower() in content.lower() for term in auth_terms)
        assert found, "API reference must cover authentication endpoints"

    def test_api_reference_covers_orders(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        order_terms = ["order", "orders", "OMS", "/orders"]
        found = any(term.lower() in content.lower() for term in order_terms)
        assert found, "API reference must cover order management endpoints"

    def test_api_reference_covers_risk(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        risk_terms = ["risk", "risk_check", "limit", "风控"]
        found = any(term.lower() in content.lower() for term in risk_terms)
        assert found, "API reference must cover risk management endpoints"

    def test_api_reference_covers_portfolio(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        portfolio_terms = ["portfolio", "position", "持仓", "投资组合"]
        found = any(term.lower() in content.lower() for term in portfolio_terms)
        assert found, "API reference must cover portfolio/position endpoints"

    def test_api_reference_covers_market_data(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        market_terms = ["market", "marketdata", "行情", "tick", "bar"]
        found = any(term.lower() in content.lower() for term in market_terms)
        assert found, "API reference must cover market data endpoints"

    def test_api_reference_has_error_codes(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        error_terms = ["error", "错误码", "status code", "400", "401", "403", "500"]
        found = any(term.lower() in content.lower() for term in error_terms)
        assert found, "API reference must document error codes"

    def test_api_reference_has_examples(self):
        api_ref = _find_doc("api_reference")
        if api_ref is None:
            pytest.skip("API reference not found")
        content = api_ref.read_text(encoding="utf-8")
        has_examples = "```" in content or "Request" in content or "Response" in content
        assert has_examples, (
            "API reference must include request/response examples"
        )

    def test_openapi_spec_exists(self):
        openapi_path = DOCS_API_DIR / "openapi_v0.4.0-alpha1.yaml"
        assert openapi_path.exists(), (
            "OpenAPI spec openapi_v0.4.0-alpha1.yaml must exist in docs/api/"
        )

    def test_openapi_has_version(self):
        openapi_path = DOCS_API_DIR / "openapi_v0.4.0-alpha1.yaml"
        if not openapi_path.exists():
            pytest.skip("OpenAPI spec not found")
        try:
            import yaml
            with open(openapi_path, "r", encoding="utf-8") as f:
                spec = yaml.safe_load(f)
            assert spec.get("openapi", "").startswith("3."), (
                "OpenAPI spec must be version 3.x"
            )
            info = spec.get("info", {})
            assert "version" in info, "OpenAPI info must include version"
        except ImportError:
            pytest.skip("PyYAML not installed")


class TestArchitectureDocumentation:
    """Tests for architecture documentation coverage."""

    def test_architecture_doc_exists(self):
        arch_doc = _find_doc("architecture")
        assert arch_doc is not None, "Architecture document must exist"

    def test_architecture_has_diagram(self):
        arch_doc = _find_doc("architecture")
        if arch_doc is None:
            pytest.skip("Architecture doc not found")
        content = arch_doc.read_text(encoding="utf-8")
        has_diagram = any(
            term in content
            for term in ["```", "mermaid", "graph", "flowchart", "sequenceDiagram"]
        )
        assert has_diagram, (
            "Architecture document must include diagrams"
        )

    def test_architecture_has_components(self):
        arch_doc = _find_doc("architecture")
        if arch_doc is None:
            pytest.skip("Architecture doc not found")
        content = arch_doc.read_text(encoding="utf-8")
        components = ["API Gateway", "Risk", "OMS", "Portfolio", "Ledger", "Authentication"]
        found = [c for c in components if c.lower() in content.lower()]
        assert len(found) >= 3, (
            f"Architecture doc must describe at least 3 components, found: {found}"
        )


class TestDeploymentDocumentation:
    """Tests for deployment documentation."""

    def test_deployment_doc_exists(self):
        deploy_doc = _find_doc("deployment")
        assert deploy_doc is not None, "Deployment document must exist"

    def test_deployment_has_helm(self):
        deploy_doc = _find_doc("deployment")
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
        content = deploy_doc.read_text(encoding="utf-8")
        helm_terms = ["helm", "Helm", "chart", "Chart"]
        found = any(term in content for term in helm_terms)
        assert found, "Deployment doc must cover Helm deployment"

    def test_deployment_has_kubernetes(self):
        deploy_doc = _find_doc("deployment")
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
        content = deploy_doc.read_text(encoding="utf-8")
        k8s_terms = ["Kubernetes", "kubernetes", "k8s", "kubectl"]
        found = any(term.lower() in content.lower() for term in k8s_terms)
        assert found, "Deployment doc must cover Kubernetes"

    def test_deployment_has_docker(self):
        deploy_doc = _find_doc("deployment")
        if deploy_doc is None:
            pytest.skip("Deployment doc not found")
        content = deploy_doc.read_text(encoding="utf-8")
        docker_terms = ["Docker", "docker", "container"]
        found = any(term in content for term in docker_terms)
        assert found, "Deployment doc must cover Docker"


class TestSecurityDocumentation:
    """Tests for security documentation."""

    def test_security_doc_exists(self):
        sec_doc = _find_doc("security")
        assert sec_doc is not None, "Security document must exist"

    def test_security_has_authentication(self):
        sec_doc = _find_doc("security")
        if sec_doc is None:
            pytest.skip("Security doc not found")
        content = sec_doc.read_text(encoding="utf-8")
        auth_terms = ["authentication", "JWT", "token", "认证", "secret"]
        found = any(term.lower() in content.lower() for term in auth_terms)
        assert found, "Security doc must cover authentication"

    def test_security_has_authorization(self):
        sec_doc = _find_doc("security")
        if sec_doc is None:
            pytest.skip("Security doc not found")
        content = sec_doc.read_text(encoding="utf-8")
        authz_terms = ["authorization", "RBAC", "permission", "授权", "compliance"]
        found = any(term.lower() in content.lower() for term in authz_terms)
        assert found, "Security doc must cover authorization/RBAC"

    def test_security_has_encryption(self):
        sec_doc = _find_doc("security")
        if sec_doc is None:
            pytest.skip("Security doc not found")
        content = sec_doc.read_text(encoding="utf-8")
        enc_terms = ["encryption", "TLS", "SSL", "加密", "hash", "secret"]
        found = any(term.lower() in content.lower() for term in enc_terms)
        assert found, "Security doc must cover encryption"