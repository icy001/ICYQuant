from .result import RecoveryResult


class RecoveryManager:
    def __init__(self, reader, replay):
        self.reader = reader
        self.replay = replay

    def recover(self, request):
        events = self.reader.read(request)
        self.replay.replay(events)

        return RecoveryResult(
            request.aggregate_id,
            len(events),
            True
        )