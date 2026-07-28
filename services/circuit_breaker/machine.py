from .state import CircuitState


class CircuitStateMachine:
    def __init__(self):
        self.state = CircuitState.CLOSED

    def open(self):
        self.state = CircuitState.OPEN

    def half_open(self):
        self.state = CircuitState.HALF_OPEN

    def close(self):
        self.state = CircuitState.CLOSED

    def current(self):
        return self.state
