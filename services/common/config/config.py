from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = True

    class Config:
        env_file = ".env"
