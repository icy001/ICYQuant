"""ICYQuant Trigger Engine — unified trigger abstraction for distributed scheduling.

The trigger engine is the *when* layer of the scheduler. It normalizes every
activation source (cron, interval, calendar, event, webhook, manual, dependency)
into a single evaluation-dispatch pipeline.

Architecture::

    SchedulerEngine
           │
    TriggerEngine
           │
    ┌──────┼──────┐
    Time  Calendar  Event
    └──────┼──────┘
           │
    PriorityQueue
           │
    SchedulerRuntime → Workflow Engine
"""

from .trigger_engine import TriggerEngine, TriggerEngineState
from .trigger_manager import TriggerManager, TriggerManagerState
from .trigger_context import TriggerContext, create_trigger_context
from .trigger_registry import TriggerRegistry
from .trigger_factory import TriggerFactory
from .trigger_validator import TriggerValidator, TriggerValidationError
from .trigger_dispatcher import TriggerDispatcher, DispatchResult

from .cron_trigger import CronTrigger
from .cron_parser import CronParser
from .cron_expression import CronExpression, CronField
from .interval_trigger import IntervalTrigger

from .calendar_trigger import CalendarTrigger
from .trading_calendar import TradingCalendar, Market
from .session_calendar import SessionCalendar, TradingSession
from .holiday_calendar import HolidayCalendar, Holiday
from .market_calendar import MarketCalendar

from .event_trigger import EventTrigger
from .manual_trigger import ManualTrigger
from .webhook_trigger import WebhookTrigger
from .dependency_trigger import DependencyTrigger, DependencyPolicy

from .priority_queue import PriorityQueue, QueueItem
from .trigger_scheduler import TriggerScheduler
from .misfire_handler import MisfireHandler, MisfirePolicy
from .retry_policy import RetryPolicy, BackoffStrategy
from .trigger_simulator import TriggerSimulator

from .metrics import TriggerMetrics
from .telemetry import TriggerTelemetry
from .diagnostics import TriggerDiagnostics
from .health import TriggerHealth

__all__ = [
    # Core engine
    "TriggerEngine",
    "TriggerEngineState",
    "TriggerManager",
    "TriggerManagerState",
    "TriggerContext",
    "create_trigger_context",
    "TriggerRegistry",
    "TriggerFactory",
    "TriggerValidator",
    "TriggerValidationError",
    "TriggerDispatcher",
    "DispatchResult",
    # Time triggers
    "CronTrigger",
    "CronParser",
    "CronExpression",
    "CronField",
    "IntervalTrigger",
    # Calendar triggers
    "CalendarTrigger",
    "TradingCalendar",
    "Market",
    "SessionCalendar",
    "TradingSession",
    "HolidayCalendar",
    "Holiday",
    "MarketCalendar",
    # Event triggers
    "EventTrigger",
    "ManualTrigger",
    "WebhookTrigger",
    "DependencyTrigger",
    "DependencyPolicy",
    # Scheduling infrastructure
    "PriorityQueue",
    "QueueItem",
    "TriggerScheduler",
    "MisfireHandler",
    "MisfirePolicy",
    "RetryPolicy",
    "BackoffStrategy",
    "TriggerSimulator",
    # Observability
    "TriggerMetrics",
    "TriggerTelemetry",
    "TriggerDiagnostics",
    "TriggerHealth",
]
