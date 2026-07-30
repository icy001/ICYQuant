"""Batch Scheduler — dynamic batching for inference throughput optimization.

Groups individual prediction requests into batches for more efficient
GPU/CPU utilization. Supports configurable batch sizes and timeout-based
flushing for latency-sensitive online serving.

Usage::

    scheduler = BatchScheduler(config=BatchConfig(max_batch_size=64, max_wait_ms=10))
    scheduler.start(batch_predict_fn)
    future = scheduler.submit({"symbol": "NVDA", "features": {...}})
    result = future.result()
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BatchConfig:
    """Batch scheduler configuration.

    Attributes:
        max_batch_size: Max requests per batch.
        max_wait_ms: Max time to wait before flushing a partial batch.
        min_batch_size: Minimum batch size to flush early (0 = wait for max_wait).
        num_workers: Number of batch processing workers.
        queue_capacity: Max pending individual requests.
        enable_dynamic_batching: Whether to adjust batch size based on load.
    """

    max_batch_size: int = 64
    max_wait_ms: float = 10.0
    min_batch_size: int = 1
    num_workers: int = 2
    queue_capacity: int = 10000
    enable_dynamic_batching: bool = True


@dataclass
class BatchRequest:
    """A single request within a batch."""

    request_id: int = 0
    symbol: str = ""
    features: Dict[str, float] = field(default_factory=dict)
    submitted_at: float = field(default_factory=time.time)


@dataclass
class BatchResult:
    """Result for a single request within a batch."""

    request_id: int = 0
    symbol: str = ""
    prediction: Optional[float] = None
    confidence: Optional[float] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class _BatchFuture:
    """Future-like object for batched request results."""

    def __init__(self, request_id: int):
        self.request_id = request_id
        self._event = threading.Event()
        self._result: Optional[BatchResult] = None

    def set_result(self, result: BatchResult) -> None:
        self._result = result
        self._event.set()

    def result(self, timeout: Optional[float] = None) -> BatchResult:
        if self._event.wait(timeout):
            return self._result or BatchResult(request_id=self.request_id, error="no result")
        return BatchResult(request_id=self.request_id, error="timeout")


class BatchScheduler:
    """Dynamic batching scheduler for inference.

    Buffers individual prediction requests and groups them into batches
    for efficient model inference. Flushes batches on size threshold or
    timeout to maintain low latency.

    Usage::

        def batch_predict(batch: List[Dict]) -> List[Dict]:
            features_list = [b["features"] for b in batch]
            results = model.predict(features_list)
            return [{"prediction": r} for r in results]

        scheduler = BatchScheduler(config=BatchConfig(max_batch_size=64))
        scheduler.start(batch_predict)
        future = scheduler.submit("NVDA", {"ema20": 182.3})
        result = future.result(timeout=0.5)
    """

    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()
        self._queue: queue.Queue = queue.Queue(maxsize=self.config.queue_capacity)
        self._futures: Dict[int, _BatchFuture] = {}
        self._batch_predict_fn: Optional[Callable] = None
        self._request_counter: int = 0
        self._lock = threading.Lock()
        self._running = False
        self._threads: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._stats: Dict[str, Any] = {
            "total_requests": 0,
            "total_batches": 0,
            "avg_batch_size": 0.0,
            "avg_latency_ms": 0.0,
        }

    def start(self, batch_predict_fn: Callable[[List[Dict[str, Any]]], List[Any]]) -> None:
        """Start the batch scheduler.

        Args:
            batch_predict_fn: Function that takes a list of request dicts
                             and returns a list of result dicts/values.
        """
        if self._running:
            return

        self._batch_predict_fn = batch_predict_fn
        self._running = True
        self._stop_event.clear()

        for i in range(self.config.num_workers):
            t = threading.Thread(target=self._batch_worker, name=f"batch-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        """Stop all batch workers."""
        self._stop_event.set()
        self._running = False
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads.clear()

    def submit(self, symbol: str, features: Dict[str, float]) -> _BatchFuture:
        """Submit a single prediction request for batching.

        Args:
            symbol: Entity identifier.
            features: Feature dict.

        Returns:
            _BatchFuture to retrieve the result.
        """
        with self._lock:
            self._request_counter += 1
            request_id = self._request_counter

        future = _BatchFuture(request_id)
        self._futures[request_id] = future

        self._queue.put(BatchRequest(request_id=request_id, symbol=symbol, features=features))

        return future

    def submit_batch(self, requests: List[Dict[str, Any]]) -> List[_BatchFuture]:
        """Submit multiple requests for batching.

        Args:
            requests: List of {"symbol": ..., "features": ...} dicts.

        Returns:
            List of futures in same order.
        """
        futures = []
        for req in requests:
            future = self.submit(req["symbol"], req.get("features", {}))
            futures.append(future)
        return futures

    def _batch_worker(self) -> None:
        """Worker that collects requests into batches and executes."""
        while not self._stop_event.is_set():
            batch: List[BatchRequest] = []
            batch_start = time.time()

            # Collect requests up to max_batch_size or timeout
            while len(batch) < self.config.max_batch_size:
                elapsed = (time.time() - batch_start) * 1000

                if len(batch) >= self.config.min_batch_size and elapsed >= self.config.max_wait_ms:
                    break

                try:
                    req = self._queue.get(timeout=self.config.max_wait_ms / 1000.0)
                    batch.append(req)
                except queue.Empty:
                    if len(batch) >= self.config.min_batch_size:
                        break
                    if (time.time() - batch_start) * 1000 >= self.config.max_wait_ms and batch:
                        break
                    # Keep waiting if no requests collected yet
                    if self._stop_event.is_set():
                        return
                    continue

            if not batch:
                continue

            # Execute batch inference
            predict_start = time.perf_counter()
            try:
                if self._batch_predict_fn:
                    # Build batch input
                    batch_input = [{"symbol": r.symbol, "features": r.features} for r in batch]
                    results = self._batch_predict_fn(batch_input)

                    # Distribute results
                    for i, req in enumerate(batch):
                        if i < len(results):
                            pred = results[i]
                            if isinstance(pred, dict):
                                value = pred.get("prediction", pred)
                                conf = pred.get("confidence")
                            else:
                                value = float(pred)
                                conf = None
                            result = BatchResult(
                                request_id=req.request_id,
                                symbol=req.symbol,
                                prediction=float(value) if value is not None else None,
                                confidence=conf,
                                latency_ms=(time.perf_counter() - predict_start) * 1000,
                            )
                        else:
                            result = BatchResult(
                                request_id=req.request_id,
                                symbol=req.symbol,
                                error="batch index out of range",
                            )

                        future = self._futures.pop(req.request_id, None)
                        if future:
                            future.set_result(result)
                else:
                    # No predict function: return mock results
                    for req in batch:
                        result = BatchResult(
                            request_id=req.request_id,
                            symbol=req.symbol,
                            prediction=0.75,
                            latency_ms=0.0,
                        )
                        future = self._futures.pop(req.request_id, None)
                        if future:
                            future.set_result(result)

            except Exception as e:
                for req in batch:
                    result = BatchResult(request_id=req.request_id, symbol=req.symbol, error=str(e))
                    future = self._futures.pop(req.request_id, None)
                    if future:
                        future.set_result(result)

            # Update stats
            batch_latency = (time.perf_counter() - predict_start) * 1000
            with self._lock:
                self._stats["total_batches"] += 1
                self._stats["total_requests"] += len(batch)
                n = self._stats["total_batches"]
                self._stats["avg_batch_size"] = self._stats["total_requests"] / n if n > 0 else 0
                old_avg = self._stats["avg_latency_ms"]
                self._stats["avg_latency_ms"] = old_avg + (batch_latency - old_avg) / n

    def get_stats(self) -> Dict[str, Any]:
        """Get batch scheduler statistics."""
        with self._lock:
            stats = dict(self._stats)
        stats["queue_size"] = self._queue.qsize()
        stats["pending_futures"] = len(self._futures)
        stats["running"] = self._running
        return stats
