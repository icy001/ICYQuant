"""
ICYQuant Batch Inference — High-throughput batch prediction service.

Handles large-scale batch inference for research and daily processing:
  - Parallel execution with configurable concurrency
  - Chunked processing for large datasets
  - Progress tracking and checkpointing
  - Resource-aware scheduling
  - Output streaming
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class BatchStatus(str, Enum):
    """Batch inference job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"       # Some succeeded, some failed
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchConfig:
    """Batch inference configuration."""
    max_concurrency: int = 50
    chunk_size: int = 256
    max_retries: int = 2
    retry_delay_ms: int = 100
    timeout_per_sample_ms: int = 10000
    progress_interval: int = 100  # Report progress every N samples
    save_checkpoints: bool = True
    output_format: str = "dict"  # dict, dataframe, csv


@dataclass
class BatchResult:
    """Result of a batch inference job."""
    batch_id: str
    model_id: str
    model_version: str
    status: BatchStatus
    total_samples: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_seconds: float = 0.0
    throughput: float = 0.0  # samples per second

    @property
    def success_rate(self) -> float:
        return self.succeeded / max(self.processed, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "status": self.status.value,
            "total_samples": self.total_samples,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4),
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "throughput": round(self.throughput, 2),
        }


# ---------------------------------------------------------------------------
# Batch Inference
# ---------------------------------------------------------------------------

class BatchInference:
    """High-throughput batch prediction service.

    Usage::

        batch = BatchInference(engine)
        result = await batch.run(
            model_id="nvda_model",
            features_list=features_list,
            version="v2.1",
        )
        print(f"Processed {result.succeeded}/{result.total_samples} samples")
    """

    def __init__(
        self,
        engine,  # InferenceEngine (lazy ref to avoid circular)
        config: Optional[BatchConfig] = None,
    ):
        self.engine = engine
        self.config = config or BatchConfig()
        self._initialized = False

        # Active jobs
        self._jobs: Dict[str, BatchResult] = {}

        # Stream callbacks
        self._on_progress: Optional[Callable[[BatchResult], None]] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("BatchInference initialized — concurrency=%d", self.config.max_concurrency)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(
        self,
        model_id: str,
        features_list: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        config: Optional[BatchConfig] = None,
    ) -> BatchResult:
        """Run batch inference on a list of feature sets.

        Args:
            model_id: Model identifier.
            features_list: List of feature dictionaries.
            version: Optional pinned model version.
            config: Batch configuration override.

        Returns:
            BatchResult with all predictions and stats.
        """
        cfg = config or self.config
        batch_id = str(uuid.uuid4())

        result = BatchResult(
            batch_id=batch_id,
            model_id=model_id,
            model_version=version or "production",
            status=BatchStatus.RUNNING,
            total_samples=len(features_list),
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self._jobs[batch_id] = result
        start_time = time.time()

        try:
            # Split into chunks
            chunks = [
                features_list[i:i + cfg.chunk_size]
                for i in range(0, len(features_list), cfg.chunk_size)
            ]

            semaphore = asyncio.Semaphore(cfg.max_concurrency)

            async def process_one(
                idx: int,
                features: Dict[str, Any],
            ) -> None:
                """Process a single sample with retry."""
                async with semaphore:
                    for attempt in range(cfg.max_retries + 1):
                        try:
                            prediction = await asyncio.wait_for(
                                self.engine.predict(
                                    model_id=model_id,
                                    features=features,
                                    version=version,
                                ),
                                timeout=cfg.timeout_per_sample_ms / 1000.0,
                            )
                            result.predictions.append({
                                "index": idx,
                                "prediction": prediction,
                            })
                            result.succeeded += 1
                            return
                        except asyncio.TimeoutError:
                            if attempt == cfg.max_retries:
                                raise
                            await asyncio.sleep(cfg.retry_delay_ms / 1000.0 * (2 ** attempt))
                        except Exception:
                            if attempt == cfg.max_retries:
                                raise
                            await asyncio.sleep(cfg.retry_delay_ms / 1000.0 * (2 ** attempt))

            # Process all chunks
            for chunk_idx, chunk in enumerate(chunks):
                tasks = []
                for i, features in enumerate(chunk):
                    global_idx = chunk_idx * cfg.chunk_size + i
                    task = asyncio.create_task(process_one(global_idx, features))
                    tasks.append(task)

                results_list = await asyncio.gather(*tasks, return_exceptions=True)

                for i, r in enumerate(results_list):
                    result.processed += 1
                    if isinstance(r, Exception):
                        result.failed += 1
                        result.errors.append({
                            "index": chunk_idx * cfg.chunk_size + i,
                            "error": str(r),
                        })

                # Progress reporting
                if cfg.progress_interval > 0 and chunk_idx % max(1, cfg.progress_interval // cfg.chunk_size) == 0:
                    elapsed = time.time() - start_time
                    throughput = result.processed / max(elapsed, 0.001)
                    logger.info(
                        "Batch progress: %d/%d (%.1f%%, %.1f samples/s)",
                        result.processed, result.total_samples,
                        result.processed / max(result.total_samples, 1) * 100,
                        throughput,
                    )
                    if self._on_progress:
                        self._on_progress(result)

            # Finalize
            elapsed = time.time() - start_time
            result.total_duration_seconds = elapsed
            result.throughput = result.processed / max(elapsed, 0.001)
            result.completed_at = datetime.now(timezone.utc).isoformat()

            if result.failed == 0:
                result.status = BatchStatus.COMPLETED
            elif result.succeeded > 0:
                result.status = BatchStatus.PARTIAL
            else:
                result.status = BatchStatus.FAILED

            # Sort predictions by index
            result.predictions.sort(key=lambda x: x["index"])

            logger.info(
                "Batch completed: %s — %d/%d succeeded (%.1f%%, %.1f samples/s)",
                batch_id, result.succeeded, result.total_samples,
                result.success_rate * 100, result.throughput,
            )

            return result

        except Exception as exc:
            result.status = BatchStatus.FAILED
            result.completed_at = datetime.now(timezone.utc).isoformat()
            logger.exception("Batch inference failed: %s", batch_id)
            raise

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        model_id: str,
        features_iterable: AsyncIterator[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        max_concurrency: int = 10,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream predictions as features arrive.

        Args:
            model_id: Model identifier.
            features_iterable: Async iterator of feature dicts.
            version: Optional pinned version.
            max_concurrency: Max concurrent inferences.

        Yields:
            Prediction results as they complete.
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        pending: List[asyncio.Task] = []

        async for features in features_iterable:
            async def predict_one(f: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    return await self.engine.predict(
                        model_id=model_id,
                        features=f,
                        version=version,
                    )

            task = asyncio.create_task(predict_one(features))
            pending.append(task)

            # Drain completed tasks if too many pending
            if len(pending) >= max_concurrency * 2:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    yield await t

        # Drain remaining
        for task in asyncio.as_completed(pending):
            yield await task

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_progress(self, callback: Callable[[BatchResult], None]) -> None:
        self._on_progress = callback

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_job(self, batch_id: str) -> Optional[BatchResult]:
        return self._jobs.get(batch_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._jobs.values()]

    def cancel_job(self, batch_id: str) -> bool:
        job = self._jobs.get(batch_id)
        if job and job.status == BatchStatus.RUNNING:
            job.status = BatchStatus.CANCELLED
            return True
        return False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        running = sum(1 for j in self._jobs.values() if j.status == BatchStatus.RUNNING)
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_jobs": running,
            "total_jobs": len(self._jobs),
        }

    def __repr__(self) -> str:
        return f"BatchInference(jobs={len(self._jobs)})"
