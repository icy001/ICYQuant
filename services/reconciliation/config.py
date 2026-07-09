from pydantic_settings import BaseSettings


class ReconciliationSettings(BaseSettings):
    service_name: str = "reconciliation"
    version: str = "0.2.4-alpha1"
    debug: bool = True

    class Config:
        env_file = ".env"
