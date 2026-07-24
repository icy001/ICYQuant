class EvictionPolicy:

    def evict(

        self,

        cache,

        key,

    ):

        cache.storage.pop(

            key,

            None,

        )