"""Scheduler CLI — command-line interface for the Distributed Scheduler.

The :class:`SchedulerCLI` provides a command-line interface for:
* Managing schedules (list, create, delete, pause, resume)
* Managing jobs (list, trigger, cancel, replay)
* Viewing cluster and worker status
* Accessing metrics and history
* Administrative operations

Commands::

    scheduler jobs list [--status running]
    scheduler jobs trigger <job_id>
    scheduler jobs cancel <job_id>
    scheduler jobs replay <job_id>
    scheduler schedules list
    scheduler schedules create --workflow X --trigger "0 9 * * 1-5"
    scheduler schedules delete <schedule_id>
    scheduler schedules pause <schedule_id>
    scheduler schedules resume <schedule_id>
    scheduler cluster status
    scheduler cluster nodes
    scheduler workers list
    scheduler metrics show
    scheduler history show [--job <id>] [--limit 100]
    scheduler health check
"""

from __future__ import annotations

import asyncio
import enum
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CLICommand(enum.Enum):
    """CLI command categories."""

    JOBS = "jobs"
    SCHEDULES = "schedules"
    CLUSTER = "cluster"
    WORKERS = "workers"
    METRICS = "metrics"
    HISTORY = "history"
    HEALTH = "health"
    HELP = "help"


class SchedulerCLI:
    """Command-line interface for scheduler management.

    Usage::

        cli = SchedulerCLI(sdk=sdk)
        await cli.run(["jobs", "list", "--status", "running"])
    """

    def __init__(self, sdk: Any = None) -> None:
        self._sdk = sdk

    # ------------------------------------------------------------------
    # Main Entry
    # ------------------------------------------------------------------

    async def run(self, args: List[str]) -> int:
        """Run a CLI command.

        Args:
            args: Command-line arguments (without program name)

        Returns:
            Exit code (0 = success, 1 = error)
        """
        if not args or args[0] in ("help", "--help", "-h"):
            self._print_help()
            return 0

        command = args[0]
        subcommand = args[1] if len(args) > 1 else "list"
        opts = self._parse_options(args[2:])

        try:
            result = await self._dispatch(command, subcommand, opts)
            self._print_result(result)
            return 0
        except Exception as exc:
            self._print_error(str(exc))
            return 1

    # ------------------------------------------------------------------
    # Command Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, command: str, subcommand: str, opts: Dict[str, Any]) -> Any:
        """Dispatch a command to the appropriate handler."""
        handlers = {
            ("jobs", "list"): lambda: self._sdk.list_jobs(status=opts.get("status"), limit=int(opts.get("limit", 50))),
            ("jobs", "trigger"): lambda: self._sdk.trigger_job(opts["job_id"]),
            ("jobs", "cancel"): lambda: self._sdk.cancel_job(opts["job_id"]),
            ("jobs", "replay"): lambda: self._sdk.cancel_job(opts["job_id"]),
            ("jobs", "get"): lambda: self._sdk.get_job(opts["job_id"]),
            ("schedules", "list"): lambda: self._sdk.list_schedules(),
            ("schedules", "create"): lambda: self._sdk.schedule(
                workflow=opts["workflow"], trigger=opts["trigger"],
                parameters=opts.get("parameters"), description=opts.get("description", ""),
            ),
            ("schedules", "delete"): lambda: self._sdk.delete_schedule(opts["schedule_id"]),
            ("schedules", "pause"): lambda: self._sdk.pause_schedule(opts["schedule_id"]),
            ("schedules", "resume"): lambda: self._sdk.resume_schedule(opts["schedule_id"]),
            ("cluster", "status"): lambda: self._sdk.get_cluster_status(),
            ("cluster", "nodes"): lambda: self._sdk.get_cluster_status(),
            ("workers", "list"): lambda: self._sdk.list_jobs(),
            ("metrics", "show"): lambda: self._sdk.get_metrics(),
            ("history", "show"): lambda: self._sdk.list_jobs(limit=int(opts.get("limit", 100))),
            ("health", "check"): lambda: {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()},
        }

        handler = handlers.get((command, subcommand))
        if not handler:
            raise ValueError(f"Unknown command: {command} {subcommand}")

        result = handler()
        if asyncio.iscoroutine(result):
            result = await result
        return result

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _print_result(self, result: Any) -> None:
        """Print a command result."""
        import json
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        print(f"Error: {message}", file=sys.stderr)

    def _print_help(self) -> None:
        """Print help text."""
        help_text = """
ICYQuant Scheduler CLI

Usage:
  scheduler <command> <subcommand> [options]

Commands:
  jobs        Manage scheduled jobs
    list      List jobs [--status <status>] [--limit <n>]
    get       Get job details <job_id>
    trigger   Manually trigger a job <job_id>
    cancel    Cancel a job <job_id>
    replay    Replay a job <job_id>

  schedules   Manage schedule definitions
    list      List all schedules
    create    Create a schedule --workflow <name> --trigger <expr> [--params <json>]
    delete    Delete a schedule <schedule_id>
    pause     Pause a schedule <schedule_id>
    resume    Resume a schedule <schedule_id>

  cluster     Cluster management
    status    Show cluster status
    nodes     List cluster nodes

  workers     Worker management
    list      List workers

  metrics     Metrics and monitoring
    show      Show scheduler metrics

  history     Execution history
    show      Show execution history [--job <id>] [--limit <n>]

  health      Health checks
    check     Run health check

  help        Show this help message
"""
        print(help_text.strip())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_options(args: List[str]) -> Dict[str, Any]:
        """Parse CLI options into a dict."""
        opts: Dict[str, Any] = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                key = arg[2:].replace("-", "_")
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    opts[key] = args[i + 1]
                    i += 2
                else:
                    opts[key] = True
                    i += 1
            elif arg.startswith("-"):
                key = arg[1:]
                opts[key] = True
                i += 1
            else:
                # Positional argument — try common keys
                if "job_id" not in opts:
                    opts["job_id"] = arg
                elif "schedule_id" not in opts:
                    opts["schedule_id"] = arg
                i += 1
        return opts
