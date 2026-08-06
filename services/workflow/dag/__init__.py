"""
DAG Execution Engine — distributed DAG execution with dependency scheduling and parallel execution.

Submodules:
- dag: Core DAG data structure
- dag_builder: Fluent builder API
- dag_compiler: Compilation pipeline (validate → optimize → sort)
- dependency_graph: Dependency relationship model
- dependency_resolver: Runtime dependency tracking
- graph_validator: Structural validation
- cycle_detector: Cycle detection (DFS)
- topological_sort: Kahn's algorithm with stage grouping
- execution_planner: Execution plan generation
- ready_queue: Priority-aware ready node queue
- scheduler: Central scheduling loop
- dispatcher: Task-to-worker dispatching
- parallel_executor: Parallel execution with fork-join
- worker_pool: Dynamic worker management
- task_executor: Unified task execution with timeout/retry
- branch_executor: Conditional branching (IF/ELSE/SWITCH/MATCH)
- condition: Condition evaluation engine
- fork: Parallel fan-out
- join: Synchronization fan-in
- retry_scheduler: Exponential backoff with jitter
- timeout_manager: Task/stage/workflow timeouts
- critical_path: CPM-based critical path analysis
- optimizer: Execution optimization passes
- metrics: Prometheus-compatible metrics
- telemetry: Unified tracing/logging/metrics
- diagnostics: Inspection and debugging tools
- health: Component health checks
"""

from services.workflow.dag.dag import DAG, DAGNode, DAGStatus
from services.workflow.dag.dag_builder import DAGBuilder
from services.workflow.dag.dag_compiler import DAGCompiler, CompilationResult
from services.workflow.dag.dependency_graph import DependencyGraph, Dependency
from services.workflow.dag.dependency_resolver import DependencyResolver
from services.workflow.dag.graph_validator import GraphValidator, ValidationResult
from services.workflow.dag.cycle_detector import CycleDetector
from services.workflow.dag.topological_sort import TopologicalSort, TopologicalResult
from services.workflow.dag.execution_planner import ExecutionPlanner, ExecutionPlan, ExecutionStrategy
from services.workflow.dag.ready_queue import ReadyQueue, QueueDiscipline
from services.workflow.dag.scheduler import Scheduler, SchedulerStatus
from services.workflow.dag.dispatcher import Dispatcher, DispatchResult
from services.workflow.dag.parallel_executor import ParallelExecutor, ParallelResult
from services.workflow.dag.worker_pool import WorkerPool, WorkerConfig, PoolMode
from services.workflow.dag.task_executor import TaskExecutor, TaskConfig, TaskResult, TaskStatus
from services.workflow.dag.branch_executor import BranchExecutor, BranchDefinition, BranchType
from services.workflow.dag.condition import Condition, ConditionGroup, ConditionEvaluator, ConditionOperator
from services.workflow.dag.fork import ForkExecutor, ForkDefinition, ForkMode
from services.workflow.dag.join import JoinExecutor, JoinDefinition, JoinMode
from services.workflow.dag.retry_scheduler import RetryScheduler, RetryPolicy, RetryStrategy
from services.workflow.dag.timeout_manager import TimeoutManager, TimeoutConfig
from services.workflow.dag.critical_path import CriticalPathAnalyzer, CriticalPathResult
from services.workflow.dag.optimizer import ExecutionOptimizer
from services.workflow.dag.metrics import DAGMetricsCollector, DAGMetricsSnapshot
from services.workflow.dag.telemetry import DAGTelemetry
from services.workflow.dag.diagnostics import DAGDiagnostics
from services.workflow.dag.health import DAGHealthChecker, HealthStatus

__all__ = [
    # Core
    "DAG", "DAGNode", "DAGStatus",
    "DAGBuilder",
    "DAGCompiler", "CompilationResult",
    "DependencyGraph", "Dependency",
    "DependencyResolver",
    # Validation
    "GraphValidator", "ValidationResult",
    "CycleDetector",
    "TopologicalSort", "TopologicalResult",
    "ExecutionPlanner", "ExecutionPlan", "ExecutionStrategy",
    # Scheduling
    "ReadyQueue", "QueueDiscipline",
    "Scheduler", "SchedulerStatus",
    "Dispatcher", "DispatchResult",
    "ParallelExecutor", "ParallelResult",
    "WorkerPool", "WorkerConfig", "PoolMode",
    "TaskExecutor", "TaskConfig", "TaskResult", "TaskStatus",
    # Control Flow
    "BranchExecutor", "BranchDefinition", "BranchType",
    "Condition", "ConditionGroup", "ConditionEvaluator", "ConditionOperator",
    "ForkExecutor", "ForkDefinition", "ForkMode",
    "JoinExecutor", "JoinDefinition", "JoinMode",
    "RetryScheduler", "RetryPolicy", "RetryStrategy",
    "TimeoutManager", "TimeoutConfig",
    # Optimization & Observability
    "CriticalPathAnalyzer", "CriticalPathResult",
    "ExecutionOptimizer",
    "DAGMetricsCollector", "DAGMetricsSnapshot",
    "DAGTelemetry",
    "DAGDiagnostics",
    "DAGHealthChecker", "HealthStatus",
]
