from enum import Enum


class SessionStatus(str, Enum):
    START = "START"
    CONNECT = "CONNECT"
    READY = "READY"
    TRADING = "TRADING"
    STOP = "STOP"


class TradingLifecycle:
    def __init__(self):
        self.status = SessionStatus.START

    def transition(self, next_status: SessionStatus) -> bool:
        valid_transitions = {
            SessionStatus.START: [SessionStatus.CONNECT],
            SessionStatus.CONNECT: [SessionStatus.READY, SessionStatus.STOP],
            SessionStatus.READY: [SessionStatus.TRADING, SessionStatus.STOP],
            SessionStatus.TRADING: [SessionStatus.STOP],
            SessionStatus.STOP: [SessionStatus.START],
        }

        if next_status in valid_transitions.get(self.status, []):
            self.status = next_status
            return True
        return False