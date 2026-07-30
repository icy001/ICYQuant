"""
ICYQuant Secret Scanner

Scans code and configuration files for exposed secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Pattern
from datetime import datetime
from enum import Enum
import logging
import re
import os

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    API_KEY = "api_key"
    DATABASE_URL = "database_url"
    PASSWORD = "password"
    TOKEN = "token"
    PRIVATE_KEY = "private_key"
    CREDIT_CARD = "credit_card"
    AWS_SECRET = "aws_secret"
    GCP_KEY = "gcp_key"
    AZURE_KEY = "azure_key"
    WEBHOOK = "webhook"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SecretFinding:
    id: str
    secret_type: SecretType
    severity: Severity
    file_path: str
    line_number: int
    snippet: str
    matched_pattern: str
    remediation: str = ""
    found_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "secretType": self.secret_type.value,
            "severity": self.severity.value,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "snippet": self.snippet,
            "remediation": self.remediation,
        }


@dataclass
class ScanResult:
    id: str
    target_path: str
    total_files_scanned: int = 0
    findings: List[SecretFinding] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    has_critical: bool = False

    def finish(self):
        self.completed_at = datetime.now()
        self.has_critical = any(f.severity == Severity.CRITICAL for f in self.findings)

    def to_dict(self) -> Dict:
        self.finish()
        return {
            "id": self.id,
            "targetPath": self.target_path,
            "totalFilesScanned": self.total_files_scanned,
            "findings": [f.to_dict() for f in self.findings],
            "hasCritical": self.has_critical,
            "startedAt": self.started_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }


class SecretScanner:
    """
    Scans code and configuration files for exposed secrets.

    Uses pattern matching to detect potential secret leakage
    in source code, configuration files, and environment files.
    """

    def __init__(self):
        self._patterns: List[Dict] = self._init_patterns()
        self._scan_history: List[ScanResult] = []
        self._max_history = 100

    def _init_patterns(self) -> List[Dict]:
        return [
            {
                "type": SecretType.API_KEY,
                "severity": Severity.CRITICAL,
                "pattern": r'(?i)(api[_\s]?key|apikey)\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']',
                "remediation": "Use environment variables or secret manager for API keys",
            },
            {
                "type": SecretType.DATABASE_URL,
                "severity": Severity.HIGH,
                "pattern": r'(?i)(database[_\s]?url|db[_\s]?url)\s*[=:]\s*["\']([a-z]+://[^"\']+)["\']',
                "remediation": "Use secret manager for database credentials",
            },
            {
                "type": SecretType.PASSWORD,
                "severity": Severity.CRITICAL,
                "pattern": r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']',
                "remediation": "Never hardcode passwords. Use secret manager",
            },
            {
                "type": SecretType.TOKEN,
                "severity": Severity.HIGH,
                "pattern": r'(?i)(token|auth[_\s]?token)\s*[=:]\s*["\']([A-Za-z0-9_\-\.]{20,})["\']',
                "remediation": "Use token manager instead of hardcoding tokens",
            },
            {
                "type": SecretType.PRIVATE_KEY,
                "severity": Severity.CRITICAL,
                "pattern": r'(-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PRIVATE)\s+PRIVATE\s+KEY-----)',
                "remediation": "Never store private keys in code. Use HSM or secret manager",
            },
            {
                "type": SecretType.CREDIT_CARD,
                "severity": Severity.HIGH,
                "pattern": r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b',
                "remediation": "Never store credit card numbers directly",
            },
            {
                "type": SecretType.AWS_SECRET,
                "severity": Severity.CRITICAL,
                "pattern": r'(?i)(aws[_\s]?secret[_\s]?key)\s*[=:]\s*["\']([A-Za-z0-9/+=]{40})["\']',
                "remediation": "Use AWS IAM roles instead of hardcoded credentials",
            },
            {
                "type": SecretType.WEBHOOK,
                "severity": Severity.MEDIUM,
                "pattern": r'(?i)(webhook[_\s]?url)\s*[=:]\s*["\'](https?://[^"\']+)["\']',
                "remediation": "Use environment variables for webhook URLs",
            },
        ]

    def scan_file(self, file_path: str) -> List[SecretFinding]:
        findings: List[SecretFinding] = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern_info in self._patterns:
                    matches = re.finditer(pattern_info["pattern"], line)
                    for match in matches:
                        finding = SecretFinding(
                            id=f"{file_path}:{line_num}:{len(findings)}",
                            secret_type=pattern_info["type"],
                            severity=pattern_info["severity"],
                            file_path=file_path,
                            line_number=line_num,
                            snippet=line.strip()[:200],
                            matched_pattern=pattern_info["pattern"],
                            remediation=pattern_info["remediation"],
                        )
                        findings.append(finding)
        except Exception as e:
            logger.warning(f"Error scanning {file_path}: {e}")
        return findings

    def scan_directory(
        self,
        directory: str,
        extensions: Optional[Set[str]] = None,
        max_files: int = 1000,
    ) -> ScanResult:
        extensions = extensions or {
            ".py", ".yaml", ".yml", ".json", ".env",
            ".conf", ".cfg", ".ini", ".toml", ".xml",
            ".js", ".ts", ".jsx", ".tsx", ".md",
        }

        result = ScanResult(target_path=directory)

        file_count = 0
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git")]
            for file in files:
                if file_count >= max_files:
                    result.finish()
                    result.total_files_scanned = file_count
                    return result

                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)
                if ext.lower() not in extensions:
                    continue

                findings = self.scan_file(file_path)
                result.findings.extend(findings)
                file_count += 1

        result.total_files_scanned = file_count
        result.finish()
        self._scan_history.append(result)
        return result

    def scan_content(self, content: str, context: str = "inline") -> List[SecretFinding]:
        findings: List[SecretFinding] = []
        for pattern_info in self._patterns:
            matches = re.finditer(pattern_info["pattern"], content)
            for match in matches:
                finding = SecretFinding(
                    id=f"{context}:{len(findings)}",
                    secret_type=pattern_info["type"],
                    severity=pattern_info["severity"],
                    file_path=context,
                    line_number=1,
                    snippet=content[:200],
                    matched_pattern=pattern_info["pattern"],
                    remediation=pattern_info["remediation"],
                )
                findings.append(finding)
        return findings

    def get_scan_history(self, limit: int = 20) -> List[Dict]:
        return [r.to_dict() for r in self._scan_history[-limit:]]

    def to_dict(self) -> Dict:
        return {
            "patternsCount": len(self._patterns),
            "scanHistoryCount": len(self._scan_history),
        }
