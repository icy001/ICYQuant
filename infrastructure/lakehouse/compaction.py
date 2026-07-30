"""ICYQuant Compaction Engine.

Compacts small files into larger ones for better query performance.
Supports:
    - Size-based compaction (merge small files)
    - Partition-level compaction
    - Background compaction scheduling
    - Compaction strategies (bin-pack, size-tiered)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CompactionStrategy(str, Enum):
    """Compaction strategies."""

    BIN_PACK = "bin_pack"          # Fill bins to target size
    SIZE_TIERED = "size_tiered"    # Merge similar-sized files
    PARTITION = "partition"        # Merge all files in a partition


@dataclass
class CompactionJob:
    """A compaction job specification."""

    job_id: str
    dataset: str
    partition: str
    input_files: List[str] = field(default_factory=list)
    output_file: str = ""
    strategy: CompactionStrategy = CompactionStrategy.BIN_PACK
    target_size_mb: int = 256
    status: str = "pending"  # pending, running, completed, failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "dataset": self.dataset,
            "partition": self.partition,
            "input_files": self.input_files,
            "output_file": self.output_file,
            "strategy": self.strategy.value,
            "target_size_mb": self.target_size_mb,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "input_size_bytes": self.input_size_bytes,
            "output_size_bytes": self.output_size_bytes,
        }


@dataclass
class CompactionResult:
    """Result of a compaction run."""

    dataset: str
    jobs_created: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    files_before: int = 0
    files_after: int = 0
    size_before_bytes: int = 0
    size_after_bytes: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "jobs_created": self.jobs_created,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "files_before": self.files_before,
            "files_after": self.files_after,
            "size_before_bytes": self.size_before_bytes,
            "size_after_bytes": self.size_after_bytes,
            "size_reduction_pct": round(
                (1 - self.size_after_bytes / max(self.size_before_bytes, 1)) * 100, 1
            ),
            "duration_ms": self.duration_ms,
        }


class CompactionEngine:
    """File Compaction Engine.

    Compacts small files into larger ones to improve query performance
    and reduce metadata overhead.

    Usage::

        engine = CompactionEngine(target_file_size_mb=256)
        jobs = engine.plan_compaction("market_tick", files)
        result = engine.run_compaction("market_tick", files)
    """

    def __init__(
        self,
        target_file_size_mb: int = 256,
        min_file_size_mb: int = 32,
        strategy: CompactionStrategy = CompactionStrategy.BIN_PACK,
    ) -> None:
        self.target_file_size_mb = target_file_size_mb
        self.min_file_size_mb = min_file_size_mb
        self.strategy = strategy
        self._jobs: Dict[str, CompactionJob] = {}
        self._history: List[CompactionResult] = []
        self._job_counter: int = 0

    # ------------------------------------------------------------------
    # Compaction Planning
    # ------------------------------------------------------------------

    def plan_compaction(
        self,
        dataset: str,
        files: List[Dict[str, Any]],
        partition: str = "",
    ) -> List[CompactionJob]:
        """Plan compaction jobs for a set of files.

        Groups small files into compaction jobs based on the strategy.

        Args:
            dataset: Dataset name.
            files: List of file info dicts (must have 'file_id' and 'size_bytes').
            partition: Partition key.

        Returns:
            List of CompactionJob.
        """
        target_bytes = self.target_file_size_mb * 1024 * 1024
        min_bytes = self.min_file_size_mb * 1024 * 1024

        # Only compact files below minimum size
        small_files = [f for f in files if f.get("size_bytes", 0) < min_bytes]
        if len(small_files) < 2:
            return []

        if self.strategy == CompactionStrategy.BIN_PACK:
            return self._plan_bin_pack(dataset, small_files, partition, target_bytes)
        elif self.strategy == CompactionStrategy.SIZE_TIERED:
            return self._plan_size_tiered(dataset, small_files, partition)
        elif self.strategy == CompactionStrategy.PARTITION:
            return self._plan_partition(dataset, small_files, partition)

        return []

    def _plan_bin_pack(
        self,
        dataset: str,
        files: List[Dict[str, Any]],
        partition: str,
        target_bytes: int,
    ) -> List[CompactionJob]:
        """Bin-pack small files into target-sized bins."""
        # Sort files by size descending (best-fit decreasing)
        files_sorted = sorted(files, key=lambda f: f.get("size_bytes", 0), reverse=True)
        bins: List[List[Dict[str, Any]]] = []
        bin_sizes: List[int] = []

        for file_info in files_sorted:
            size = file_info.get("size_bytes", 0)
            placed = False

            # Try to fit in existing bin
            for i, bin_size in enumerate(bin_sizes):
                if bin_size + size <= target_bytes:
                    bins[i].append(file_info)
                    bin_sizes[i] += size
                    placed = True
                    break

            if not placed:
                bins.append([file_info])
                bin_sizes.append(size)

        # Create jobs for bins with 2+ files
        jobs: List[CompactionJob] = []
        for i, bin_files in enumerate(bins):
            if len(bin_files) < 2:
                continue

            self._job_counter += 1
            job = CompactionJob(
                job_id=f"compaction_{self._job_counter}",
                dataset=dataset,
                partition=partition,
                input_files=[f["file_id"] for f in bin_files],
                output_file=f"compacted_{self._job_counter}.parquet",
                strategy=CompactionStrategy.BIN_PACK,
                input_size_bytes=sum(f.get("size_bytes", 0) for f in bin_files),
            )
            self._jobs[job.job_id] = job
            jobs.append(job)

        return jobs

    def _plan_size_tiered(
        self,
        dataset: str,
        files: List[Dict[str, Any]],
        partition: str,
    ) -> List[CompactionJob]:
        """Group files of similar sizes (size-tiered compaction)."""
        # Group files by size tier
        tiers: Dict[int, List[Dict[str, Any]]] = {}
        for file_info in files:
            size = file_info.get("size_bytes", 0)
            tier = 0
            while size > (self.min_file_size_mb * 1024 * 1024) * (2 ** tier):
                tier += 1
            tiers.setdefault(tier, []).append(file_info)

        jobs: List[CompactionJob] = []
        for tier, tier_files in tiers.items():
            if len(tier_files) < 2:
                continue

            self._job_counter += 1
            job = CompactionJob(
                job_id=f"compaction_{self._job_counter}",
                dataset=dataset,
                partition=partition,
                input_files=[f["file_id"] for f in tier_files],
                output_file=f"compacted_tier{tier}_{self._job_counter}.parquet",
                strategy=CompactionStrategy.SIZE_TIERED,
                input_size_bytes=sum(f.get("size_bytes", 0) for f in tier_files),
            )
            self._jobs[job.job_id] = job
            jobs.append(job)

        return jobs

    def _plan_partition(
        self,
        dataset: str,
        files: List[Dict[str, Any]],
        partition: str,
    ) -> List[CompactionJob]:
        """Merge all small files in a partition into one."""
        if len(files) < 2:
            return []

        self._job_counter += 1
        job = CompactionJob(
            job_id=f"compaction_{self._job_counter}",
            dataset=dataset,
            partition=partition,
            input_files=[f["file_id"] for f in files],
            output_file=f"compacted_partition_{self._job_counter}.parquet",
            strategy=CompactionStrategy.PARTITION,
            input_size_bytes=sum(f.get("size_bytes", 0) for f in files),
        )
        self._jobs[job.job_id] = job
        return [job]

    # ------------------------------------------------------------------
    # Compaction Execution
    # ------------------------------------------------------------------

    def run_compaction(
        self,
        dataset: str,
        files: List[Dict[str, Any]],
        partition: str = "",
    ) -> CompactionResult:
        """Plan and execute compaction for a dataset.

        Args:
            dataset: Dataset name.
            files: List of file info dicts.
            partition: Partition key.

        Returns:
            CompactionResult.
        """
        start = datetime.utcnow()

        jobs = self.plan_compaction(dataset, files, partition)

        files_before = len(files)
        size_before = sum(f.get("size_bytes", 0) for f in files)

        completed = 0
        failed = 0
        errors: List[str] = []

        for job in jobs:
            try:
                job.status = "running"
                job.started_at = datetime.utcnow()

                # Simulate compaction (in production, would merge Parquet files)
                # Output is approximately same total size with slight compression
                job.output_size_bytes = int(job.input_size_bytes * 0.85)
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                completed += 1

            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                failed += 1
                errors.append(str(e))

        # Calculate post-compaction file count
        # Each job replaces N files with 1 file
        files_removed = sum(len(j.input_files) for j in jobs if j.status == "completed")
        files_added = completed
        files_after = files_before - files_removed + files_added

        size_after = sum(
            j.output_size_bytes for j in jobs if j.status == "completed"
        ) + sum(
            f.get("size_bytes", 0) for f in files
            if f["file_id"] not in {
                fid for job in jobs if job.status == "completed"
                for fid in job.input_files
            }
        )

        duration = (datetime.utcnow() - start).total_seconds() * 1000

        result = CompactionResult(
            dataset=dataset,
            jobs_created=len(jobs),
            jobs_completed=completed,
            jobs_failed=failed,
            files_before=files_before,
            files_after=files_after,
            size_before_bytes=size_before,
            size_after_bytes=size_after,
            duration_ms=duration,
            errors=errors,
        )

        self._history.append(result)
        return result

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[CompactionJob]:
        """Get a compaction job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        dataset: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CompactionJob]:
        """List compaction jobs with optional filters."""
        jobs = list(self._jobs.values())
        if dataset:
            jobs = [j for j in jobs if j.dataset == dataset]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def get_history(self) -> List[CompactionResult]:
        """Get compaction history."""
        return list(self._history)

    def get_stats(self) -> Dict[str, Any]:
        """Get compaction statistics."""
        total_files_saved = sum(
            r.files_before - r.files_after
            for r in self._history
        )

        total_size_saved = sum(
            r.size_before_bytes - r.size_after_bytes
            for r in self._history
        )

        return {
            "total_jobs": len(self._jobs),
            "total_runs": len(self._history),
            "pending_jobs": len(self.list_jobs(status="pending")),
            "running_jobs": len(self.list_jobs(status="running")),
            "completed_jobs": len(self.list_jobs(status="completed")),
            "failed_jobs": len(self.list_jobs(status="failed")),
            "total_files_saved": total_files_saved,
            "total_size_saved_gb": round(total_size_saved / (1024 ** 3), 2),
        }
