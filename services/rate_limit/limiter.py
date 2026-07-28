class GlobalLimiter:

    def __init__(self, bucket):
        self.bucket = bucket

    def allow(self):
        return self.bucket.allow()
