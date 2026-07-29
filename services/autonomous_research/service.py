class AutonomousResearchService:
    def __init__(self, detector):
        self.detector = detector

    def discover(self, data):
        return self.detector.detect(data)
