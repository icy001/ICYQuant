class LeakyBucket:

    def __init__(self):
        self.queue = []

    def push(self, request):
        self.queue.append(request)

        return True
