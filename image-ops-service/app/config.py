from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PODI Image Ops"
    image_ops_service_token: str | None = Field(default=None, env="IMAGE_OPS_SERVICE_TOKEN")
    image_ops_host: str = Field(default="127.0.0.1", env="IMAGE_OPS_HOST")
    image_ops_port: int = Field(default=8301, env="IMAGE_OPS_PORT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
