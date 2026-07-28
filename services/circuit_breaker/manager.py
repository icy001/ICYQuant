class CircuitBreakerManager:
    def __init__(self, detector, machine, recovery):
        self.detector = detector
        self.machine = machine
        self.recovery = recovery

    def record_failure(self, failure, config):
        if self.detector.detect(failure, config):
            self.machine.open()
        return self.machine.current()

    def recover(self):
        return self.recovery.recover(self.machine)
