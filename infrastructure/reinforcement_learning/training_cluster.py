"""Infrastructure: RL Training Cluster.

Manages training cluster resources for large-scale RL experiments:
- Computing resource allocation
- Job scheduling and queuing
- Resource monitoring
- Cross-node synchronization
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import time
import json
import queue
import threading
import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class ClusterNodeStatus(Enum):
    """Status of a cluster node."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class JobPriority(Enum):
    """Job priority level."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class JobState(Enum):
    """Job execution state."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class NodeResources:
    """Computing resources on a node."""

    cpu_cores: int = 4
    cpu_used: float = 0.0
    memory_gb: float = 16.0
    memory_used_gb: float = 0.0
    gpu_count: int = 1
    gpu_used: int = 0

    def available_cpu(self) -> float:
        return self.cpu_cores - self.cpu_used

    def available_memory(self) -> float:
        return self.memory_gb - self.memory_used_gb

    def available_gpu(self) -> int:
        return self.gpu_count - self.gpu_used

    def can_allocate(self, cpu_needed: float = 1, memory_needed: float = 1) -> bool:
        return (
            self.available_cpu() >= cpu_needed
            and self.available_memory() >= memory_needed
        )


@dataclass
class ClusterNode:
    """A node in the training cluster."""

    node_id: str
    host: str = "localhost"
    port: int = 8000
    status: ClusterNodeStatus = ClusterNodeStatus.ONLINE
    resources: NodeResources = field(default_factory=NodeResources)

    # Metrics
    jobs_completed: int = 0
    jobs_failed: int = 0
    total_train_steps: int = 0
    avg_job_time: float = 0.0
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class ClusterJob:
    """A job scheduled on the training cluster."""

    job_id: str
    job_type: str = "training"  # training, eval, selfplay, optimize
    priority: JobPriority = JobPriority.NORMAL
    state: JobState = JobState.QUEUED

    # Resource requirements
    cpu_needed: float = 2.0
    memory_needed_gb: float = 4.0
    gpu_needed: int = 1

    # Execution
    assigned_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout_seconds: int = 3600

    # Callback
    on_complete: Optional[Any] = None

    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return 0.0


@dataclass
class ClusterConfig:
    """Configuration for training cluster."""

    cluster_id: str = "rl_training_cluster"
    max_nodes: int = 8
    max_jobs_per_node: int = 4

    # Scheduling
    scheduling_policy: str = "priority_fifo"  # priority_fifo, round_robin, least_loaded
    preempt_low_priority: bool = False

    # Health
    heartbeat_interval_seconds: int = 30
    node_timeout_seconds: int = 120

    # Logging
    log_dir: str = "./cluster_logs"


class TrainingCluster:
    """Manages a cluster of compute resources for RL training.

    Handles node registration, job scheduling, resource allocation,
    and health monitoring.

    Usage:
        cluster = TrainingCluster(config)
        cluster.register_node("node1", resources=NodeResources(cpu_cores=8))
        job_id = cluster.submit_job(ClusterJob(job_id="train_1"))
        cluster.wait_for_job(job_id)
        cluster.shutdown()
    """

    def __init__(self, config: Optional[ClusterConfig] = None):
        self.config = config or ClusterConfig()
        self._nodes: Dict[str, ClusterNode] = {}
        self._jobs: Dict[str, ClusterJob] = {}
        self._job_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._lock = threading.Lock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        import os
        os.makedirs(self.config.log_dir, exist_ok=True)

    def start(self):
        """Start the cluster scheduler and monitor."""
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Training cluster '{self.config.cluster_id}' started")

    def shutdown(self):
        """Stop the cluster."""
        self._running = False
        for job_id, job in self._jobs.items():
            if job.state == JobState.RUNNING:
                job.state = JobState.INTERRUPTED
                job.error = "Cluster shutting down"
        logger.info("Training cluster shut down")

    def register_node(
        self,
        node_id: str,
        host: str = "localhost",
        port: int = 8000,
        resources: Optional[NodeResources] = None,
    ) -> ClusterNode:
        """Register a new compute node."""
        with self._lock:
            if len(self._nodes) >= self.config.max_nodes:
                raise RuntimeError(f"Max nodes ({self.config.max_nodes}) reached")

            node = ClusterNode(
                node_id=node_id,
                host=host,
                port=port,
                resources=resources or NodeResources(),
            )
            self._nodes[node_id] = node
            logger.info(f"Node '{node_id}' registered at {host}:{port}")
            return node

    def unregister_node(self, node_id: str):
        """Remove a node from the cluster."""
        with self._lock:
            self._nodes.pop(node_id, None)

            # Re-queue jobs assigned to this node
            for job in list(self._jobs.values()):
                if job.assigned_node == node_id and job.state == JobState.RUNNING:
                    job.state = JobState.QUEUED
                    job.assigned_node = None
                    self._enqueue_job(job)

    def submit_job(self, job: ClusterJob) -> str:
        """Submit a job to the cluster queue.

        Returns:
            job_id
        """
        with self._lock:
            self._jobs[job.job_id] = job
            self._enqueue_job(job)
            logger.info(f"Job {job.job_id} submitted (priority={job.priority.value})")
            return job.job_id

    def get_job_status(self, job_id: str) -> Optional[JobState]:
        """Get status of a job."""
        job = self._jobs.get(job_id)
        return job.state if job else None

    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get result of a completed job."""
        job = self._jobs.get(job_id)
        if job and job.state == JobState.COMPLETED:
            return job.result
        return None

    def wait_for_job(self, job_id: str, timeout: Optional[float] = None):
        """Wait for a specific job to complete."""
        start = time.time()
        while True:
            job = self._jobs.get(job_id)
            if not job:
                return
            if job.state in (JobState.COMPLETED, JobState.FAILED):
                return
            if timeout and (time.time() - start) > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            time.sleep(0.1)

    def cancel_job(self, job_id: str):
        """Cancel a queued or running job."""
        job = self._jobs.get(job_id)
        if job and job.state in (JobState.QUEUED, JobState.RUNNING):
            job.state = JobState.FAILED
            job.error = "Cancelled by user"
            if job.assigned_node:
                self._release_resources(job.assigned_node, job)

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get overall cluster status."""
        with self._lock:
            node_stats = []
            for node in self._nodes.values():
                node_stats.append({
                    "node_id": node.node_id,
                    "status": node.status.value,
                    "cpu_used": node.resources.cpu_used,
                    "cpu_total": node.resources.cpu_cores,
                    "memory_used": node.resources.memory_used_gb,
                    "memory_total": node.resources.memory_gb,
                    "gpu_used": node.resources.gpu_used,
                    "gpu_total": node.resources.gpu_count,
                    "jobs_completed": node.jobs_completed,
                })

            job_states = {}
            for job in self._jobs.values():
                s = job.state.value
                job_states[s] = job_states.get(s, 0) + 1

            return {
                "cluster_id": self.config.cluster_id,
                "nodes": node_stats,
                "total_nodes": len(self._nodes),
                "active_nodes": sum(
                    1 for n in self._nodes.values()
                    if n.status == ClusterNodeStatus.ONLINE
                ),
                "jobs": job_states,
                "total_jobs": len(self._jobs),
                "queue_size": self._job_queue.qsize(),
            }

    def _scheduler_loop(self):
        """Main scheduling loop."""
        while self._running:
            try:
                self._schedule_next_jobs()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time.sleep(1)

    def _monitor_loop(self):
        """Health monitoring loop."""
        while self._running:
            try:
                self._check_node_health()
                self._check_job_timeouts()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(self.config.heartbeat_interval_seconds)

    def _schedule_next_jobs(self):
        """Schedule jobs from queue to available nodes."""
        with self._lock:
            available_nodes = [
                n for n in self._nodes.values()
                if n.status == ClusterNodeStatus.ONLINE
                and self._get_node_load(n) < self.config.max_jobs_per_node
            ]

            while not self._job_queue.empty() and available_nodes:
                _, job = self._job_queue.get()
                if job.state != JobState.QUEUED:
                    continue

                node = self._select_node(available_nodes, job)
                if node is None:
                    self._enqueue_job(job)  # Re-queue
                    break

                if node.resources.can_allocate(job.cpu_needed, job.memory_needed_gb):
                    self._assign_job(job, node)
                else:
                    self._enqueue_job(job)

    def _select_node(
        self, nodes: List[ClusterNode], job: ClusterJob
    ) -> Optional[ClusterNode]:
        """Select best node for a job based on scheduling policy."""
        if not nodes:
            return None

        policy = self.config.scheduling_policy

        if policy == "least_loaded":
            return min(nodes, key=lambda n: self._get_node_load(n))
        elif policy == "round_robin":
            # Simple round-robin
            idx = hash(job.job_id) % len(nodes)
            return nodes[idx]
        else:  # priority_fifo - pick first available
            for node in nodes:
                if node.resources.can_allocate(job.cpu_needed, job.memory_needed_gb):
                    return node
            return None

    def _assign_job(self, job: ClusterJob, node: ClusterNode):
        """Assign a job to a node."""
        job.state = JobState.RUNNING
        job.assigned_node = node.node_id
        job.started_at = time.time()

        node.resources.cpu_used += job.cpu_needed
        node.resources.memory_used_gb += job.memory_needed_gb
        node.resources.gpu_used += job.gpu_needed

        logger.info(f"Job {job.job_id} assigned to node {node.node_id}")

        # Simulate job execution in a thread
        thread = threading.Thread(
            target=self._execute_job, args=(job,), daemon=True
        )
        thread.start()

    def _execute_job(self, job: ClusterJob):
        """Execute a job (simulation)."""
        try:
            # In production, this would connect to the node and run training
            # Here we simulate with a sleep
            simulated_time = min(job.timeout_seconds * 0.1, 10.0)
            time.sleep(simulated_time)

            job.state = JobState.COMPLETED
            job.completed_at = time.time()
            job.result = {
                "status": "completed",
                "duration": job.duration_seconds(),
                "steps": 1000,
                "reward": np.random.uniform(0, 10),
            }

            if job.on_complete:
                try:
                    job.on_complete(job.result)
                except Exception as e:
                    logger.error(f"Job callback error: {e}")

        except Exception as e:
            job.state = JobState.FAILED
            job.error = str(e)
            logger.error(f"Job {job.job_id} execution failed: {e}")

        finally:
            if job.assigned_node:
                self._release_resources(job.assigned_node, job)

            # Update node stats
            node = self._nodes.get(job.assigned_node or "")
            if node:
                if job.state == JobState.COMPLETED:
                    node.jobs_completed += 1
                else:
                    node.jobs_failed += 1

    def _release_resources(self, node_id: str, job: ClusterJob):
        """Release resources back to the node."""
        node = self._nodes.get(node_id)
        if node:
            node.resources.cpu_used = max(0, node.resources.cpu_used - job.cpu_needed)
            node.resources.memory_used_gb = max(0, node.resources.memory_used_gb - job.memory_needed_gb)
            node.resources.gpu_used = max(0, node.resources.gpu_used - job.gpu_needed)

    def _enqueue_job(self, job: ClusterJob):
        """Add job to priority queue."""
        # Negative priority for max-heap behavior in PriorityQueue
        self._job_queue.put((-job.priority.value, job))

    def _get_node_load(self, node: ClusterNode) -> float:
        """Get current load on a node."""
        cpu_load = node.resources.cpu_used / max(node.resources.cpu_cores, 1)
        mem_load = node.resources.memory_used_gb / max(node.resources.memory_gb, 1)
        running_jobs = sum(
            1 for j in self._jobs.values()
            if j.assigned_node == node.node_id and j.state == JobState.RUNNING
        )
        return (cpu_load + mem_load + running_jobs / self.config.max_jobs_per_node) / 3

    def _check_node_health(self):
        """Check health of all nodes."""
        with self._lock:
            now = time.time()
            for node in self._nodes.values():
                if now - node.last_heartbeat > self.config.node_timeout_seconds:
                    if node.status != ClusterNodeStatus.OFFLINE:
                        node.status = ClusterNodeStatus.OFFLINE
                        logger.warning(f"Node {node.node_id} timed out (last heartbeat: {node.last_heartbeat})")

    def _check_job_timeouts(self):
        """Check for timed-out jobs."""
        with self._lock:
            for job in list(self._jobs.values()):
                if job.state != JobState.RUNNING:
                    continue
                if job.started_at and (time.time() - job.started_at) > job.timeout_seconds:
                    job.state = JobState.FAILED
                    job.error = f"Job timed out after {job.timeout_seconds}s"
                    logger.warning(f"Job {job.job_id} timed out")
                    if job.assigned_node:
                        self._release_resources(job.assigned_node, job)
