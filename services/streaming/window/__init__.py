"""Window package — window types and manager for the streaming platform."""

from .tumbling_window import TumblingWindow, WindowResult
from .sliding_window import SlidingWindow
from .session_window import SessionWindow
from .global_window import GlobalWindow, TriggerType
from .window_manager import WindowManager, WindowConfig, WindowType

__all__ = [
    "TumblingWindow",
    "SlidingWindow",
    "SessionWindow",
    "GlobalWindow",
    "TriggerType",
    "WindowResult",
    "WindowManager",
    "WindowConfig",
    "WindowType",
]
