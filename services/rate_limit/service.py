from .limiter import GlobalLimiter


class RateLimiterService:

    def __init__(
        self,
        repository,
        limiter
    ):
        self.repository = repository
        self.limiter = limiter

    def check(self):
        return self.limiter.allow()
