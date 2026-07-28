class CacheSynchronizer:

    def sync(
        self,
        local,
        distributed
    ):
        distributed.update(local)

        return distributed
