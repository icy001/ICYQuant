class AdaptiveLimiter:

    def adjust(
        self,
        cpu,
        memory
    ):
        if cpu > 90:
            return "STRICT"

        return "NORMAL"
