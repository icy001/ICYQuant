"""Worker Pool — concurrent inference worker management.

Manages a pool of inference workers for parallel prediction execution.
Supports health monitoring, auto-restart, and load-aware work distribution.

Usage::

    pool = WorkerPool(config=WorkerConfig(num_workers=4))
    pool.start(predict_fn)
    result = pool.submit({"symbol": "NVDA", "features": {...}})
    pool.stop()
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class WorkerStatus(str, Enum):
    """Inference worker status."""
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkerConfig:
    """Worker pool configuration.

    Attributes:
        num_workers: Number of inference workers.
        max_queue_size: Max pending requests.
        request_timeout_ms: Per-request timeout.
        health_check_interval: Seconds between health checks.
        auto_restart: Restart failed workers.
    """

    num_workers: int = 4
    max_queue_size: int = 1000
    request_timeout_ms: int = 500
    health_check_interval: float = 10.0
    auto_restart: bool = True


class InferenceWorker:
    """A single inference worker thread.

    Pulls requests from a shared queue, executes prediction,
    and puts results back.
    """

    def __init__(self, worker_id: int, predict_fn: Callable, request_queue: queue.Queue, result_queue: queue.Queue):
        self.worker_id = worker_id
        self._predict_fn = predict_fn
        self._request_queue = request_queue
        self._result_queue = result_queue
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.status: WorkerStatus = WorkerStatus.IDLE
        self._processed_count: int = 0
        self._error_count: int = 0
        self._started_at: float = 0.0

    def start(self) -> None:
        """Start the worker thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=f"inference-worker-{self.worker_id}", daemon=True)
        self._started_at = time.time()
        self.status = WorkerStatus.IDLE
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self.status = WorkerStatus.STOPPED

    def _run(self) -> None:
        """Main worker loop."""
        while not self._stop_event.is_set():
            try:
                request_id, task = self._request_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            self.status = WorkerStatus.BUSY
            start = time.perf_counter()

            try:
                result = self._predict_fn(task)
                latency = (time.perf_counter() - start) * 1000
                self._result_queue.put((request_id, result, latency, None))
                self._processed_count += 1
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                self._result_queue.put((request_id, None, latency, str(e)))
                self._error_count += 1

            self.status = WorkerStatus.IDLE
            self._request_queue.task_done()

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "processed": self._processed_count,
            "errors": self._error_count,
            "uptime_seconds": round(time.time() - self._started_at, 1) if self._started_at > 0 else 0,
        }


class WorkerPool:
    """Manages a pool of concurrent inference workers.

    Distributes prediction requests across multiple workers for
    parallel execution. Supports health monitoring and auto-restart.

    Usage::

        pool = WorkerPool(config=WorkerConfig(num_workers=4))
        pool.start(lambda task: serving_service.predict(task["symbol"]))
        result = pool.submit({"symbol": "NVDA", "features": {...}})
        pool.stop()
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig()
        self._workers: List[InferenceWorker] = []
        self._request_queue: queue.Queue = queue.Queue(maxsize=self.config.max_queue_size)
        self._result_queue: queue.Queue = queue.Queue()
        self._predict_fn: Optional[Callable] = None
        self._request_counter: int = 0
        self._lock = threading.Lock()
        self._running = False

    def start(self, predict_fn: Callable[[Dict[str, Any]], Any]) -> None:
        """Start the worker pool.

        Args:
            predict_fn: Function that takes a task dict and returns a result.
        """
        if self._running:
            return

        self._predict_fn = predict_fn
        self._running = True

        for i in range(self.config.num_workers):
            worker = InferenceWorker(i, predict_fn, self._request_queue, self._result_queue)
            worker.start()
            self._workers.append(worker)

    def stop(self) -> None:
        """Stop all workers gracefully."""
        self._running = False
        for worker in self._workers:
            worker.stop()
        self._workers.clear()

    def submit(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a prediction task and wait for result.

        Args:
            task: Task dict with 'symbol' and 'features'.

        Returns:
            Result dict with 'prediction', 'confidence', 'latency_ms'.
        """
        with self._lock:
            self._request_counter += 1
            request_id = self._request_counter

        try:
            self._request_queue.put((request_id, task), timeout=self.config.request_timeout_ms / 1000.0)
            result_id, result, latency, error = self._result_queue.get(timeout=self.config.request_timeout_ms / 1000.0)

            if error:
                return {"prediction": None, "error": error, "latency_ms": latency}
            return {"prediction": result, "latency_ms": latency}

        except queue.Full:
            return {"prediction": None, "error": "Worker pool full", "latency_ms": 0}
        except queue.Empty:
            return {"prediction": None, "error": "Request timeout", "latency_ms": self.config.request_timeout_ms}

    def submit_batch(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submit multiple tasks in parallel.

        Args:
            tasks: List of task dicts.

        Returns:
            List of result dicts (order preserved).
        """
        futures = []
        for task in tasks:
            with self._lock:
                self._request_counter += 1
                request_id = self._request_counter
            try:
                self._request_queue.put((request_id, task), timeout=1.0)
                futures.append(request_id)
            except queue.Full:
                futures.append(-1)

        # Collect results
        results: Dict[int, Dict[str, Any]] = {}
        for _ in futures:
            try:
                result_id, result, latency, error = self._result_queue.get(timeout=5.0)
                results[result_id] = {
                    "prediction": result,
                    "latency_ms": latency,
                    "error": error,
                }
            except queue.Empty:
                break

        return [results.get(fid, {"prediction": None, "error": "no result"}) for fid in futures]

    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics."""
        return {
            "num_workers": len(self._workers),
            "queue_size": self._request_queue.qsize(),
            "running": self._running,
            "workers": [w.stats for w in self._workers],
        }

    def health_check(self) -> bool:
        """Check health of all workers. Restarts failed ones if configured."""
        all_healthy = True
        for worker in self._workers:
            if worker.status == WorkerStatus.ERROR and self.config.auto_restart:
                worker.stop()
                worker.start()
                all_healthy = False
            elif worker.status == WorkerStatus.ERROR:
                all_healthy = False
        return all_healthy
