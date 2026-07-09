import redis


class RedisCache:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        self.client = redis.Redis(host=host, port=port, db=db)

    def get(self, key: str):
        value = self.client.get(key)
        return value.decode("utf-8") if value else None

    def set(self, key: str, value: str, ex: int = None):
        self.client.set(key, value, ex=ex)

    def delete(self, key: str):
        self.client.delete(key)

    def incr(self, key: str):
        return self.client.incr(key)
