class CacheManager:

    def __init__(

        self,

        l1,

        l2,

    ):

        self.l1 = l1

        self.l2 = l2

    def get(

        self,

        key,

    ):

        value = self.l1.get(key)

        if value:

            return value

        value = self.l2.get(key)

        if value:

            self.l1.put(

                key,

                value,

            )

        return value