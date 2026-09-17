"""The ICYQuant ↔ LEAN boundary.

This adapter is deliberately thin, and deliberately *optional*: ICYQuant
starts, researches and validates without LEAN, without Docker and
without a QuantConnect organisation.  When LEAN *is* present, this is
the only place that knows about it.

  ICYQuant owns                     LEAN owns
  -------------------------------   ------------------------------
  Alpha / Strategy / Risk           Security / Market data
  StrategyContract / sizing         Order / Fill / Portfolio
                                    Paper Brokerage

Nothing here places an order.  LEAN owns order submission; the adapter
writes the contract, probes the toolchain, and constructs the command —
which is exactly what makes P0-01 testable on a Mac with no LEAN CLI at
all.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .contract import StrategyContract
from .mapper import contract_to_lean_payload

__all__ = ["CONTRACT_FILENAME", "LeanAdapter"]

#: The file the LEAN algorithm reads back.
CONTRACT_FILENAME = "strategy_contract.json"

PROBE_TIMEOUT_SECONDS = 10


class LeanAdapter:
    """Thin boundary between ICYQuant and LEAN."""

    def __init__(
        self,
        project_dir: str | Path,
        lean_binary: str = "lean",
        docker_binary: str = "docker",
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.lean_binary = lean_binary
        self.docker_binary = docker_binary

    # ── environment ────────────────────────────────────────────────
    def health(self) -> dict[str, Any]:
        """Report whether LEAN can actually run here.

        ``status`` is one of ``OK`` (CLI usable), ``UNAVAILABLE`` (CLI
        not installed — the expected state on a fresh Mac) or ``ERROR``
        (installed but broken).  Docker is reported separately because
        ``lean live deploy`` shells out to the Docker engine.
        """
        binary = shutil.which(self.lean_binary)

        if binary is None:
            return {
                "status": "UNAVAILABLE",
                "lean_binary": self.lean_binary,
                "detail": f"{self.lean_binary!r} not found on PATH",
                "docker": self._docker_health(),
                "project_dir": str(self.project_dir),
            }

        try:
            result = subprocess.run(
                [self.lean_binary, "--version"],
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            return {
                "status": "ERROR",
                "lean_binary": binary,
                "detail": str(exc),
                "docker": self._docker_health(),
                "project_dir": str(self.project_dir),
            }

        return {
            "status": "OK" if result.returncode == 0 else "ERROR",
            "lean_binary": binary,
            "version": (result.stdout or "").strip(),
            "returncode": result.returncode,
            "stderr": (result.stderr or "").strip() or None,
            "docker": self._docker_health(),
            "project_dir": str(self.project_dir),
        }

    def _docker_health(self) -> dict[str, Any]:
        binary = shutil.which(self.docker_binary)

        if binary is None:
            return {"status": "UNAVAILABLE"}

        try:
            result = subprocess.run(
                [self.docker_binary, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            return {"status": "ERROR", "detail": str(exc)}

        if result.returncode != 0:
            return {
                "status": "ERROR",
                "detail": (result.stderr or "").strip() or "docker engine unreachable",
            }

        return {"status": "OK", "server_version": (result.stdout or "").strip()}

    # ── contract ───────────────────────────────────────────────────
    def write_contract(
        self,
        contract: StrategyContract,
        filename: str = CONTRACT_FILENAME,
    ) -> Path:
        """Validate, serialise and persist the contract for LEAN."""
        contract.validate()

        self.project_dir.mkdir(parents=True, exist_ok=True)

        path = self.project_dir / filename
        payload = contract_to_lean_payload(contract)

        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return path

    def read_contract(self, filename: str = CONTRACT_FILENAME) -> dict[str, Any]:
        """Read back what was written (used by the E2E suite)."""
        path = self.project_dir / filename

        if not path.exists():
            raise FileNotFoundError(path)

        return json.loads(path.read_text(encoding="utf-8"))

    # ── deployment ─────────────────────────────────────────────────
    def build_live_command(
        self,
        *,
        contract_path: Optional[Path] = None,
        output_dir: Optional[str | Path] = None,
        brokerage: str = "Paper Trading",
    ) -> list[str]:
        """The ``lean live deploy`` argv for a paper deployment.

        Paper Trading needs no broker API, no credentials and no real
        money — but the local live-deployment workflow itself is gated
        behind a QuantConnect organisation, which is why P0-01 keeps
        this command *constructible* without being *required*.
        """
        command = [
            self.lean_binary,
            "live",
            "deploy",
            str(self.project_dir),
            "--brokerage",
            brokerage,
        ]

        if contract_path is not None:
            command.extend(
                [
                    "--parameter",
                    "strategy_contract",
                    Path(contract_path).name,
                ]
            )

        if output_dir is not None:
            command.extend(["--output", str(output_dir)])

        return command

    def deploy_paper(
        self,
        contract: StrategyContract,
        *,
        output_dir: Optional[str | Path] = None,
        cwd: Optional[str | Path] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the paper deployment to completion.

        A live deployment is long-running, so this call blocks until
        LEAN exits.  The P0-01 suite never calls it — it builds the
        command and hands it to the operator instead.
        """
        if contract.mode != "paper":
            raise ValueError("LeanAdapter.deploy_paper requires mode='paper'")

        contract_path = self.write_contract(contract)

        command = self.build_live_command(
            contract_path=contract_path,
            output_dir=output_dir,
        )

        return subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else str(self.project_dir.parent),
            text=True,
            check=False,
        )
